/**
 * Arcadian ERP Service Worker
 * Powered by Workbox
 */

importScripts('https://storage.googleapis.com/workbox-cdn/releases/6.4.1/workbox-sw.js');
importScripts('https://unpkg.com/dexie@3.2.2/dist/dexie.js');

const db = new Dexie("ArcadianOfflineDB");
db.version(2).stores({
    snapshots: "table_name, updated_at",
    actions: "++id, timestamp, status",
    config: "key"
});

// 1. Instant Activation
self.addEventListener('install', (event) => {
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(clients.claim());
});

// 2. Cache Administrative Assets (CSS, JS, Fonts)
workbox.routing.registerRoute(
    ({request}) => request.destination === 'script' || request.destination === 'style' || request.destination === 'font' || request.destination === 'image',
    new workbox.strategies.StaleWhileRevalidate({
        cacheName: 'static-resources',
    })
);

// 3. Cache Admin Pages (NetworkFirst for fresh data, falling back to cache offline)
const adminStrategy = new workbox.strategies.NetworkFirst({
    cacheName: 'admin-pages',
    networkTimeoutSeconds: 5, // Fallback to cache if network is slow
    plugins: [
        new workbox.expiration.ExpirationPlugin({
            maxEntries: 200, // Increased for full-site offline
            maxAgeSeconds: 24 * 60 * 60, // 24 Hours
        }),
    ],
});

workbox.routing.registerRoute(
    ({url}) => {
        // Exclude login and logout from caching to prevent CSRF and stale session issues
        const isLoginLogout = url.pathname.includes('/login/') || url.pathname.includes('/logout/');
        return url.pathname.startsWith('/admin/') && !isLoginLogout;
    },
    async (params) => {
        try {
            return await adminStrategy.handle(params);
        } catch (error) {
            // If both fail, return a custom offline response or the cached dashboard if available
            return caches.match('/admin/') || new Response('Offline: Resource not cached.', {
                status: 503,
                statusText: 'Service Unavailable',
                headers: new Headers({'Content-Type': 'text/plain'})
            });
        }
    }
);

// 3. Background Sync & Message Handling
self.addEventListener('message', (event) => {
    if (event.data.type === 'SYNC_ACTIONS') {
        console.log("SW Message Received: SYNC_ACTIONS trigger.");
        event.waitUntil(replayActionQueue());
    } else if (event.data.type === 'CLEAR_CACHE') {
        console.log("SW Message Received: CLEAR_CACHE trigger.");
        event.waitUntil(
            // Only clear admin-pages to prevent stale data; keep static-resources for performance
            caches.delete('admin-pages').then(() => {
                console.log("SW: admin-pages cache cleared successfully.");
            })
        );
    }
});

/**
 * Broadcasts a message to all controlled tabs.
 */
async function broadcastMessage(message) {
    const clients = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    clients.forEach(client => {
        client.postMessage(message);
    });
}

let isSyncing = false;
async function replayActionQueue() {
    if (isSyncing) {
        console.log("SW Sync: Already in progress, skipping concurrent call.");
        return;
    }
    isSyncing = true;

    // Check if we are in manual debug offline mode
    try {
        const debugConfig = await db.config.get('debug_offline');
        if (debugConfig && debugConfig.value === true) {
            console.warn("SW Sync: Suppressed (Debug Offline Mode is active).");
            isSyncing = false;
            return;
        }
    } catch (e) {
        console.debug("Config check failed, proceeding with sync.");
    }

    const actions = await db.actions.where("status").equals("pending").toArray();
    
    if (actions.length === 0) {
        console.log("No pending actions to sync.");
        isSyncing = false;
        return;
    }

    console.log(`Sync started: Processing ${actions.length} pending actions.`);
    await broadcastMessage({ type: 'SYNC_STARTED', count: actions.length });

    let successCount = 0;
    for (const action of actions) {
        let attempts = 0;
        let success = false;
        
        while (attempts < 2 && !success) {
            try {
                console.log(`Attempting to sync action ${action.id} (Attempt ${attempts + 1}): ${action.url}`);
                
                // Construct the body from the array of pairs
                const searchParams = new URLSearchParams();
                if (Array.isArray(action.data)) {
                    action.data.forEach(([key, value]) => {
                        searchParams.append(key, value);
                    });
                } else {
                    // Fallback for legacy simple object data
                    Object.entries(action.data).forEach(([key, value]) => {
                        searchParams.append(key, value);
                    });
                }

                // Append the requestId to the body as well for robustness
                if (action.requestId) {
                    searchParams.append('x_client_request_id', action.requestId);
                }

                console.log(`Replay Payload: ${searchParams.toString().substring(0, 200)}...`);

                const headers = {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-Client-Request-ID': action.requestId
                };

                // Add CSRF token if captured
                if (action.csrfToken) {
                    headers['X-CSRFToken'] = action.csrfToken;
                    console.debug(`Sync: Adding captured CSRF token to headers.`);
                }

                const response = await fetch(action.url, {
                    method: action.method,
                    headers: headers,
                    credentials: 'include',
                    body: searchParams.toString()
                });

                if (response.ok) {
                    await db.actions.delete(action.id);
                    successCount++;
                    success = true;
                    console.log(`Successfully synced action ${action.id}`);
                } else {
                    const errorText = await response.text();
                    console.error(`Failed to sync action ${action.id}. Status: ${response.status}. Body: ${errorText.substring(0, 200)}`);
                    
                    if (response.status === 403 || response.status === 401) {
                        console.warn("Session expired or CSRF failure. Pausing sync.");
                        isSyncing = false;
                        await broadcastMessage({ type: 'SYNC_ERROR', status: response.status, message: "AUTH_REQUIRED" });
                        return; // Stop processing entirely
                    } else if (response.status >= 500) {
                        console.warn("Server error. Item remains pending for retry.");
                        isSyncing = false;
                        // Keep as pending for later
                        return; 
                    } else {
                        // 400, 404, 405 etc - permanent client failure
                        console.error("Permanent failure. Marking action as failed.");
                        await db.actions.update(action.id, { status: 'failed', error: errorText.substring(0, 100) });
                        isSyncing = false;
                        return; // Stop serial processing
                    }
                }
            } catch (error) {
                attempts++;
                console.error(`Network error during sync for ${action.id} (Attempt ${attempts}):`, error);
                
                // If it's a true network error (not a 4xx/5xx handled above)
                if (attempts >= 2) {
                    console.warn("SW: Network appears dead. Broadcasting to frontend.");
                    isSyncing = false;
                    await broadcastMessage({ type: 'SYNC_ERROR', message: "NETWORK_UNAVAILABLE" });
                }

                if (attempts < 2) {
                    await new Promise(r => setTimeout(r, 1000));
                }
            }
        }
        
        if (!success) {
            console.error(`Maximum attempts reached for action ${action.id}. (Networking issue).`);
            break;
        }
    }
    
    isSyncing = false;

    // If we successfully synced actions, the 'admin-pages' cache is now stale.
    // Clear it so the next navigation gets fresh data from the server.
    if (successCount > 0) {
        console.log(`SW: ${successCount} actions synced. Clearing stale admin-pages cache...`);
        await caches.delete('admin-pages');
    }

    await broadcastMessage({ type: 'SYNC_FINISHED', successCount: successCount });
}

// 4. Periodic Sync Trigger
self.addEventListener('sync', (event) => {
    if (event.tag === 'sync-arcadian-actions') {
        event.waitUntil(replayActionQueue());
    }
});
