/**
 * Arcadian ERP Offline Sync Bridge
 * Handles Dexie.js (IndexedDB) and Form Interception.
 */

// 1. Initialize Dexie Database
const db = new Dexie("ArcadianOfflineDB");
db.version(2).stores({ // Increment version for new table
    snapshots: "table_name, updated_at",
    actions: "++id, timestamp, status",
    config: "key"
}).upgrade(tx => {
    // Migration logic if needed
});

// 2. Global State & Constants
const OFFLINE_CLASS = 'is-offline';
const SYNC_ACTION_TYPE = 'SYNC_ACTIONS';
const DEBUG_OFFLINE_KEY = 'ARC_DEBUG_OFFLINE';
const LAST_STATE_KEY = 'ARC_LAST_OFFLINE_STATE';

/**
 * Robust check for connectivity that supports a persistent debug flag.
 * This ensures "Offline" status survives page navigations and refreshes.
 */
function isOffline() {
    const onlineStatus = navigator.onLine;
    const debugFlag = localStorage.getItem(DEBUG_OFFLINE_KEY);
    const lastOffline = sessionStorage.getItem(LAST_STATE_KEY) === 'true';

    const result = !onlineStatus || debugFlag === 'true' || lastOffline;
    if (result) {
        console.debug(`isOffline check: true (onLine: ${onlineStatus}, debugFlag: ${debugFlag}, lastOffline: ${lastOffline})`);
    }
    return result;
}

/**
 * Force the UI into Offline mode based on a real-world failure (e.g. fetch failed)
 * even if navigator.onLine is lying.
 */
function forceOfflineMode(reason = "unknown") {
    if (!document.body.classList.contains(OFFLINE_CLASS)) {
        console.warn(`Force Offline Mode [${reason}]: Adjusting UI state.`);
        document.body.classList.add(OFFLINE_CLASS);
        updatePendingBadge();
    }
}

/**
 * Real connectivity check. Do NOT use /admin/* URLs here: the service worker
 * NetworkFirst strategy can satisfy those from cache while the real network is down,
 * which makes the app think it is "online" and skips the offline queue.
 */
async function checkTrulyOnline() {
    if (!navigator.onLine) return false;
    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 2000);
        const url = `/api/v1/ping/?t=${Date.now()}`;
        const res = await fetch(url, {
            method: "GET",
            cache: "no-store",
            credentials: "same-origin",
            signal: controller.signal,
        });
        clearTimeout(timeoutId);
        return res.ok;
    } catch (e) {
        console.debug("Network Probe: Failed. We are functionally offline.", e);
        return false;
    }
}

let isNetworkProbeInProgress = false;
/**
 * Synchronizes the UI state with the real network condition by probing.
 */
async function syncStateWithNetwork(reason = "unknown") {
    if (isNetworkProbeInProgress) return;
    isNetworkProbeInProgress = true;

    try {
        const trulyOnline = await checkTrulyOnline();
        const debugFlag = localStorage.getItem(DEBUG_OFFLINE_KEY) === 'true';
        
        const shouldBeOffline = !trulyOnline || debugFlag;
        const currentUIOffline = document.body.classList.contains(OFFLINE_CLASS);

        console.log(`[Offline UI] syncStateWithNetwork [${reason}]: trulyOnline=${trulyOnline}, debugFlag=${debugFlag}, currentlyOffline=${currentUIOffline}`);

        const statusText = document.getElementById("status-text");

        if (shouldBeOffline) {
            if (!currentUIOffline) {
                console.warn(`[Offline UI] State Sync [${reason}]: Network dead or DEBUG active. Forcing OFFLINE.`);
                document.body.classList.add(OFFLINE_CLASS);
                sessionStorage.setItem(LAST_STATE_KEY, 'true');
                updatePendingBadge();
            }
            if (statusText) statusText.textContent = "Offline";
        } else {
            if (currentUIOffline) {
                console.log(`[Offline UI] State Sync [${reason}]: Network RESTORED. Transitioning to ONLINE.`);
                document.body.classList.remove(OFFLINE_CLASS);
                sessionStorage.setItem(LAST_STATE_KEY, 'false');
                triggerSync(reason);
            }
            if (statusText) statusText.textContent = "Online";
        }
    } finally {
        isNetworkProbeInProgress = false;
    }
}

/**
 * Starts a periodic check to handle "Ghost Online" scenarios where
 * events don't fire correctly in simulated environments.
 */
function startHeartbeat() {
    setInterval(() => {
        const navOnline = navigator.onLine;
        const uiOffline = document.body.classList.contains(OFFLINE_CLASS);
        
        // If there's a mismatch OR we are offline (check for recovery faster)
        if ((navOnline && uiOffline) || uiOffline) {
            syncStateWithNetwork("heartbeat_check");
        }
    }, 3000); // 3 second heartbeat
}
window.ARC_OFFLINE = async function(state) {
    console.warn(`ARC_OFFLINE called with: ${state}`);
    if (state) {
        localStorage.setItem(DEBUG_OFFLINE_KEY, 'true');
        await db.config.put({ key: 'debug_offline', value: true });
        document.body.classList.add(OFFLINE_CLASS);
        console.warn("DEBUG: Persistent Offline Mode ENABLED.");
    } else {
        localStorage.setItem(DEBUG_OFFLINE_KEY, 'false'); // Explicitly set to false instead of removing
        await db.config.delete('debug_offline');
        document.body.classList.remove(OFFLINE_CLASS);
        console.log("DEBUG: Persistent Offline Mode DISABLED. Triggering sync...");
        triggerSync();
    }
    await updatePendingBadge();
};

/**
 * Helper to get a cookie value by name (e.g. csrftoken)
 */
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// 3. Form Interception Logic
let lastClickedButton = null;
let isProcessingSubmission = false;
let bypassOfflineInterceptor = false;

// Global Click listener to capture which "Submit" button was used in Django Admin
// (e.g. Save, Save and Continue, Save and Add Another)
document.addEventListener("click", (e) => {
    const btn = e.target.closest('button[type="submit"], input[type="submit"]');
    if (btn) {
        lastClickedButton = btn;
        console.debug(`Button Clicked: ${btn.name}=${btn.value}`);
    }
});

document.addEventListener("submit", async (event) => {
    const form = event.target;
    try {
        if (bypassOfflineInterceptor) {
            return;
        }
        if (form.method.toLowerCase() !== "post") {
            return;
        }
        event.preventDefault();

        // Always do a last-second connectivity check on submit.
        // This prevents false "online" states when devtools/network just switched.
        let offline = isOffline();
        if (!offline) {
            const trulyOnline = await checkTrulyOnline();
            offline = !trulyOnline;
            if (offline) {
                forceOfflineMode("submit_network_probe");
                sessionStorage.setItem(LAST_STATE_KEY, 'true');
            }
        }

        console.log(`Form submission intercepted. isOffline: ${offline}`);

        if (offline) {

        if (isProcessingSubmission) {
            console.warn("Prevented duplicate submission attempt.");
            return;
        }
        isProcessingSubmission = true;
        
        const formData = new FormData(form);
        
        // Convert FormData to an Array of [key, value] pairs.
        // This is superior to Object.fromEntries because it preserves multiple values for the same key
        // (e.g. ManyToMany fields, checkboxes).
        const dataEntries = [];
        formData.forEach((value, key) => {
            dataEntries.push([key, value]);
        });
        
        // CRITICAL: Include the name/value of the button that triggered the submit.
        // Django Admin uses this to determine behavior (save vs save_and_continue).
        if (lastClickedButton && lastClickedButton.name) {
            dataEntries.push([lastClickedButton.name, lastClickedButton.value]);
            console.log(`Action Meta: Found submitting button ${lastClickedButton.name}`);
        }
        
        // Unique request ID for idempotency on replay (avoid throwing if UUID unsupported)
        const requestId =
            typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
                ? crypto.randomUUID()
                : `${Date.now()}-${Math.random().toString(36).slice(2, 12)}`;
        
        try {
            console.warn("OFFLINE SAVING: Intercepting form submission...");
            
            // Debugging: Log full payload for verification
            console.group("Offline Data Capture Audit");
            console.log("Action URL:", form.action || window.location.href);
            console.table(dataEntries);
            console.groupEnd();

            const actionId = await db.actions.add({
                url: form.action || window.location.href, // Handle empty action
                method: "POST",
                data: dataEntries, // Store high-fidelity array
                timestamp: Date.now(),
                status: "pending",
                requestId: requestId,
                csrfToken: getCookie('csrftoken') // Capture current CSRF token
            });
            
            console.log(`Action #${actionId} saved to IndexedDB (High Fidelity). Triggering badge update...`);
            await updatePendingBadge();
            
            // Show feedback
            if (typeof toastr !== 'undefined') {
                toastr.warning("Offline: Action saved locally and will sync when online.");
            } else {
                alert("Offline: Action saved locally and will sync when online.");
            }
            
            // Reset state
            lastClickedButton = null;

            // Persist the offline state across redirect to prevent "Flash of Green" (Ghost Online)
            sessionStorage.setItem(LAST_STATE_KEY, 'true');
            
            // User requested to always redirect to /admin/ after offline save
            const redirectUrl = '/admin/';
            console.log(`Redirecting to central dashboard: ${redirectUrl}`);
            window.location.href = redirectUrl;
            
        } catch (error) {
            console.error("Dexie Error during offline save:", error);
            isProcessingSubmission = false; // Reset on error so user can try again
        }
        } else {
            console.log(`Form submission ONLINE after probe. Submitting to: ${form.action}`);

            // Preserve which submit button was used (save, save-and-continue, etc.).
            if (lastClickedButton && lastClickedButton.name) {
                const hidden = document.createElement("input");
                hidden.type = "hidden";
                hidden.name = lastClickedButton.name;
                hidden.value = lastClickedButton.value;
                form.appendChild(hidden);
            }

            bypassOfflineInterceptor = true;
            HTMLFormElement.prototype.submit.call(form);
        }
    } catch (error) {
        console.error("Offline submit interceptor failed; falling back to normal submit.", error);
        // Fail-open: never block core admin actions because of offline JS errors.
        bypassOfflineInterceptor = true;
        HTMLFormElement.prototype.submit.call(form);
    }
});

/**
 * Pre-fetches key URLs and dynamically discovers links in the sidebar/dashboard
 * to "warm" the Service Worker cache based on user permissions.
 */
async function warmOfflineCache() {
    if (isOffline()) {
        console.log("Discovery Crawler: Skipping (Offline Mode detected).");
        return;
    }
    
    console.log("Discovery Crawler: Starting permission-aware pre-caching...");
    
    const corePaths = ['/admin/', '/api/v1/snapshot/'];
    const discoveredLinks = new Set(corePaths);
    
    const linkSelectors = [
        '.nav-sidebar a.nav-link', // Jazzmin sidebar
        '.content-wrapper .card-body a', // Dashboard links
        'ul.object-tools a.addlink', // "Add" buttons in list views
        '#changelist-form th.field-name a', // Name links in changelists (to visit "Change" pages)
        '#content-main .app-list a.section', // Module headers in index
    ];

    linkSelectors.forEach(selector => {
        document.querySelectorAll(selector).forEach(link => {
            const url = link.getAttribute('href');
            if (url && (url.startsWith('/admin/') || url.startsWith('http://127.0.0.1:8000/admin/')) && !url.includes('logout') && !url.includes('login')) {
                // Normalize URL
                let cleanUrl = url.split('?')[0];
                if (cleanUrl.startsWith('http')) {
                    cleanUrl = new URL(cleanUrl).pathname;
                }
                discoveredLinks.add(cleanUrl);
            }
        });
    });

    console.log(`Discovery Crawler: Found ${discoveredLinks.size} paths across multiple modules. Warming cache...`);
    
    const linkArray = Array.from(discoveredLinks);
    let errorCount = 0;
    for (let i = 0; i < linkArray.length; i += 2) {
        const batch = linkArray.slice(i, i + 2);
        try {
            await Promise.all(batch.map(path => 
                fetch(path, { cache: 'no-cache', priority: 'low' }).catch(err => {
                    console.debug(`Discovery Crawler: Skipping ${path} - network is disrupted.`);
                    errorCount++;
                    throw err; // Propagate to catch block
                })
            ));
        } catch (err) {
            // If even the crawler is failing consistently, we are offline
            if (errorCount > 2) {
                forceOfflineMode("crawler_failure");
                break;
            }
        }
        await new Promise(resolve => setTimeout(resolve, 300));
    }
    console.log("Discovery Crawler: Pre-caching complete.");
}

// 4. Synchronization Trigger
/**
 * Synchronization Trigger
 * Attempts to probe the network first if we think we are offline,
 * ensuring the sync can proceed if connectivity was just restored.
 */
async function triggerSync(reason = "manual") {
    console.log(`Sync Trigger [${reason}]: Initiated.`);

    // If we think we are offline, do a quick verified probe.
    if (isOffline()) {
        const trulyOnline = await checkTrulyOnline();
        if (!trulyOnline) {
            console.warn(`Sync Trigger [${reason}]: Suppressed (App is truly Offline).`);
            if (reason === "admin_queue_modal" && typeof toastr !== 'undefined') {
                toastr.warning("Cannot sync while offline. Please restore connectivity first.");
            }
            return;
        }
        console.log(`Sync Trigger [${reason}]: Network probe succeeded. Proceeding...`);
        // Update local state to reflect recovery
        document.body.classList.remove(OFFLINE_CLASS);
        sessionStorage.setItem(LAST_STATE_KEY, 'false');
    }

    if ('serviceWorker' in navigator) {
        try {
            const registration = await navigator.serviceWorker.ready;
            
            // 1. Always send an immediate message to the SW to start sync NOW.
            if (registration.active) {
                console.log(`Sync Trigger [${reason}]: Sending activation message to Service Worker.`);
                registration.active.postMessage({ type: SYNC_ACTION_TYPE });
            }

            // 2. Register for Background Sync as a fallback/robustness measure.
            if (registration.sync) {
                await registration.sync.register('sync-arcadian-actions');
                console.debug(`Sync Trigger [${reason}]: Background Sync registration verified.`);
            }
        } catch (error) {
            console.error(`Sync Trigger [${reason}]: Registration failed:`, error);
        }
    } else {
        console.warn(`Sync Trigger [${reason}]: Aborted (Service Worker not supported).`);
    }
}

// 5. Sync Progress UI Logic
const SYNC_MODAL_ID = 'offline-sync-modal';
const SYNC_BADGE_ID = 'sync-badge';
const QUEUE_MODAL_ID = 'offline-queue-modal';
const QUEUE_BUTTON_ID = 'queue-inspector-btn';

function isAdminUser() {
    return window.ARC_IS_ADMIN === true;
}

async function updatePendingBadge() {
    let badge = document.getElementById(SYNC_BADGE_ID);
    
    // Defensive: If badge isn't ready, try to inject it now
    if (!badge) {
        injectIndicator();
        badge = document.getElementById(SYNC_BADGE_ID);
    }
    if (!badge) return;

    try {
        const pendingCount = await db.actions.where("status").equals("pending").count();
        const failedCount = await db.actions.where("status").equals("failed").count();
        
        console.debug(`Badge Update: ${pendingCount} pending, ${failedCount} failed.`);

        if (pendingCount > 0 || failedCount > 0) {
            let label = "";
            if (pendingCount > 0) label += `${pendingCount} PENDING`;
            if (failedCount > 0) {
                if (label) label += " / ";
                label += `${failedCount} FAILED`;
            }
            
            badge.textContent = label;
            badge.className = failedCount > 0 ? 'badge badge-danger' : 'badge badge-info';
            badge.style.display = 'inline-block';
            badge.style.cursor = failedCount > 0 ? 'pointer' : 'default';
            badge.title = failedCount > 0 ? "Click to retry failed actions" : "Pending synchronization";
            
            // Add retry listener if needed
            if (failedCount > 0) {
                badge.onclick = async () => {
                    if (confirm("Would you like to retry the failed offline actions?")) {
                        await db.actions.where("status").equals("failed").modify({ status: "pending" });
                        updatePendingBadge();
                        triggerSync();
                    }
                };
            } else {
                badge.onclick = null;
            }
        } else {
            badge.style.display = 'none';
        }
    } catch (error) {
        console.error("Error updating badge:", error);
    }
}

async function openQueueInspector() {
    try {
        if (!isAdminUser()) return;
        
        injectQueueModal();
        const modal = document.getElementById(QUEUE_MODAL_ID);
        const tbody = document.getElementById("queue-table-body");
        const summary = document.getElementById("queue-summary");
        
        if (!modal || !tbody || !summary) {
            console.error("Queue Inspector: UI elements missing.");
            return;
        }

        console.debug("Queue Inspector: Loading actions from IndexedDB...");
        const actions = await db.actions.orderBy("timestamp").reverse().toArray();
        const pending = actions.filter(a => a.status === "pending").length;
        const failed = actions.filter(a => a.status === "failed").length;
        
        summary.textContent = `Pending: ${pending} | Failed: ${failed} | Total: ${actions.length}`;

        tbody.innerHTML = "";
        if (!actions.length) {
            tbody.innerHTML = `<tr><td colspan="4" style="text-align:center; color:#666; padding: 20px;">No queued actions.</td></tr>`;
        } else {
            actions.slice(0, 100).forEach((action) => {
                const tr = document.createElement("tr");
                const when = new Date(action.timestamp || Date.now()).toLocaleString();
                const statusClass = action.status === 'failed' ? 'text-danger fw-bold' : (action.status === 'pending' ? 'text-info' : '');
                
                tr.innerHTML = `
                    <td>${action.id ?? "-"}</td>
                    <td class="${statusClass}">${action.status || "-"}</td>
                    <td style="max-width:380px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${action.url || ""}">
                        ${action.url || "-"}
                    </td>
                    <td>${when}</td>
                `;
                tbody.appendChild(tr);
            });
        }

        modal.style.display = "flex";
        console.debug("Queue Inspector: Displayed.");
    } catch (error) {
        console.error("Queue Inspector failed to open:", error);
        if (typeof toastr !== 'undefined') {
            toastr.error("Failed to load offline queue.");
        }
    }
}

function closeQueueInspector() {
    const modal = document.getElementById(QUEUE_MODAL_ID);
    if (modal) modal.style.display = "none";
}

/**
 * Injects the connectivity indicator and badge into the Jazzmin navbar.
 * This ensures the structure is always present when we need to update it.
 */
function injectIndicator() {
    if (document.getElementById("offline-indicator")) return;

    const navbar = document.querySelector('.main-header.navbar');
    if (!navbar) return;

    console.debug("Injecting premium connectivity indicator into navbar center...");
    
    const wrapper = document.createElement('div');
    wrapper.id = 'offline-indicator-wrapper';
    
    wrapper.innerHTML = `
        <div id="offline-indicator">
            <span id="status-dot" class="status-dot"></span>
            <span id="status-text">Checking...</span>
            <span id="sync-badge" class="badge" style="display:none;">0 PENDING</span>
            ${isAdminUser() ? '<button type="button" id="queue-inspector-btn" class="btn btn-sm btn-outline-primary" style="margin-left:8px; padding:2px 8px; font-size:11px;">Queue</button>' : ''}
        </div>
    `;
    navbar.appendChild(wrapper);

    if (isAdminUser()) {
        const queueBtn = document.getElementById(QUEUE_BUTTON_ID);
        if (queueBtn) {
            queueBtn.addEventListener("click", openQueueInspector);
        }
    }
}

function injectSyncModal() {
    if (document.getElementById(SYNC_MODAL_ID)) return;

    const modalHtml = `
        <div id="${SYNC_MODAL_ID}" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.5); z-index:9999; align-items:center; justify-content:center;">
            <div style="background:white; padding:30px; border-radius:8px; text-align:center; box-shadow:0 4px 12px rgba(0,0,0,0.2); max-width:400px; width:90%;">
                <div class="spinner-border text-primary mb-3" role="status" style="width: 3rem; height: 3rem;">
                    <span class="sr-only">Loading...</span>
                </div>
                <h4 style="margin-bottom:10px; color:#333;">Synchronizing Data</h4>
                <p id="sync-modal-text" style="color:#666; margin-bottom:0;">Please wait while we sync your offline changes...</p>
            </div>
        </div>
    `;
    document.body.insertAdjacentHTML('beforeend', modalHtml);
}

function injectQueueModal() {
    if (document.getElementById(QUEUE_MODAL_ID)) return;
    
    console.log("[Offline UI] Preparing Queue Modal...");
    const modalHtml = `
        <div id="${QUEUE_MODAL_ID}" class="offline-sync-modal-overlay" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.6); z-index:10000; align-items:center; justify-content:center; backdrop-filter: blur(4px);">
            <div class="offline-sync-modal-content" style="background:white; padding:25px; border-radius:12px; width:95%; max-width:1000px; max-height:85vh; overflow:hidden; display:flex; flex-direction:column; box-shadow: 0 10px 25px rgba(0,0,0,0.2);">
                <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:15px; border-bottom: 1px solid #eee; padding-bottom: 10px;">
                    <div style="display:flex; align-items:center;">
                        <i class="fas fa-history text-primary" style="font-size: 20px; margin-right: 12px;"></i>
                        <h4 style="margin:0; font-weight: 700; color: #333;">Offline Queue Inspector</h4>
                    </div>
                    <button type="button" id="queue-close-btn" class="btn btn-sm btn-secondary" style="border-radius: 20px; padding: 4px 15px;">Close</button>
                </div>
                
                <div style="background: #f8f9fa; padding: 12px 20px; border-radius: 8px; margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center;">
                    <p id="queue-summary" style="margin-bottom:0; color:#495057; font-weight: 600; font-size: 14px;"></p>
                    <div style="display:flex; gap:10px;">
                        <button type="button" id="queue-refresh-btn" class="btn btn-sm btn-outline-info" title="Refresh local list"><i class="fas fa-sync-alt"></i> Refresh</button>
                        <button type="button" id="queue-retry-failed-btn" class="btn btn-sm btn-outline-warning" title="Reset failed actions to pending"><i class="fas fa-redo"></i> Retry Failed</button>
                        <button type="button" id="queue-sync-btn" class="btn btn-sm btn-primary" style="padding-left: 20px; padding-right: 20px; font-weight: 600;"><i class="fas fa-cloud-upload-alt"></i> Sync Now</button>
                    </div>
                </div>

                <div style="flex:1; overflow-y:auto; border: 1px solid #eee; border-radius: 8px;">
                    <table class="table table-hover table-striped mb-0">
                        <thead style="position: sticky; top: 0; background: white; z-index: 10;">
                            <tr>
                                <th style="width: 80px;">ID</th>
                                <th style="width: 120px;">Status</th>
                                <th>URL</th>
                                <th style="width: 200px;">Timestamp</th>
                            </tr>
                        </thead>
                        <tbody id="queue-table-body">
                            <tr><td colspan="4" style="text-align:center; padding: 30px;">Loading actions...</td></tr>
                        </tbody>
                    </table>
                </div>
                
                <div style="margin-top: 15px; font-size: 11px; color: #999; text-align: center;">
                    Actions are stored locally in IndexedDB and replayed in order once online connectivity is verified.
                </div>
            </div>
        </div>
    `;
    document.body.insertAdjacentHTML("beforeend", modalHtml);
    console.log("[Offline UI] Queue Modal injected.");
}

function showSyncModal(text) {
    const modal = document.getElementById(SYNC_MODAL_ID);
    if (modal) {
        document.getElementById('sync-modal-text').textContent = text || "Please wait while we sync your offline changes...";
        modal.style.display = 'flex';
    }
}

function hideSyncModal() {
    const modal = document.getElementById(SYNC_MODAL_ID);
    if (modal) {
        modal.style.display = 'none';
        updatePendingBadge(); // Final refresh when modal closes
    }
}

// 6. Service Worker Communication
if ('serviceWorker' in navigator) {
    navigator.serviceWorker.addEventListener('message', (event) => {
        if (event.data.type === 'SYNC_STARTED') {
            console.log(`SW: Sync started for ${event.data.count} items.`);
            showSyncModal(`Syncing ${event.data.count} tasks... please wait for a while.`);
        } else if (event.data.type === 'SYNC_FINISHED') {
            console.log(`SW: Sync finished. Success count: ${event.data.successCount}`);
            hideSyncModal();
            updatePendingBadge();
            if (event.data.successCount > 0) {
                if (typeof toastr !== 'undefined') {
                    toastr.success(`Successfully synced ${event.data.successCount} actions.`);
                }
                // Proactively re-warm the cache with fresh data after it was cleared by SW
                setTimeout(warmOfflineCache, 500);
            }
        } else if (event.data.type === 'SYNC_ERROR') {
            console.error("SW: Sync error received", event.data);
            hideSyncModal();
            updatePendingBadge();
            
            if (event.data.message === "NETWORK_UNAVAILABLE") {
                forceOfflineMode("sw_sync_failure");
            } else if (event.data.message === "AUTH_REQUIRED") {
                if (typeof toastr !== 'undefined') {
                    toastr.error("Sync paused. You need to re-login to synchronize data.");
                } else {
                    alert("Sync paused. Please re-login to finish synchronization.");
                }
            } else {
                if (typeof toastr !== 'undefined') {
                    toastr.error("Some actions failed to sync. Check the dashboard badge.");
                }
            }
        }
    });
}

// 7. Connectivity Listeners
window.addEventListener('online', () => {
    console.log("Network Event: Browser reports ONLINE. Probing to verify...");
    syncStateWithNetwork("network_online_event");
});

window.addEventListener('offline', () => {
    console.warn("Network Event: Browser reports OFFLINE.");
    document.body.classList.add(OFFLINE_CLASS);
});

// Support BFCache (Back-Forward Cache)
window.addEventListener('pageshow', async (event) => {
    if (event.persisted) {
        console.log("Page loaded from BFCache. Refreshing offline state...");
        const offline = isOffline();
        if (offline) document.body.classList.add(OFFLINE_CLASS);
        await updatePendingBadge();
        if (!offline) triggerSync("bfcache_restore");
    }
});

// Initial Status & Sync Check on page load
document.addEventListener('DOMContentLoaded', async () => {
    // 1. Immediate State Injection (Prevents Flash of Green)
    const online = navigator.onLine;
    const debugFlag = localStorage.getItem(DEBUG_OFFLINE_KEY);
    const lastOffline = sessionStorage.getItem(LAST_STATE_KEY) === 'true';
    const isActuallyOffline = (online === false || debugFlag === 'true' || lastOffline);
    
    if (isActuallyOffline) {
        document.body.classList.add(OFFLINE_CLASS);
    }

    console.group("Arcadian Offline Initialization");
    console.log(`Navigator.onLine: ${online}, Last State: ${lastOffline}`);
    
    injectIndicator();
    injectSyncModal(); 
    await updatePendingBadge(); 
    startHeartbeat();

    if (isActuallyOffline) {
        console.warn("Status: OFFLINE MODE ACTIVE (Initializing UI)");
        const st = document.getElementById("status-text");
        if (st) st.textContent = "Offline";

        // Force a probe to confirm if we can eventually go back online
        if (online !== false && debugFlag !== 'true') {
            syncStateWithNetwork("initial_load_probe");
        }
    } else {
        // Safe check
        await syncStateWithNetwork("initial_load");
        
        if (!document.body.classList.contains(OFFLINE_CLASS)) {
            console.log("Status: ONLINE MODE ACTIVE. Warm cache and checking sync...");
            const st = document.getElementById("status-text");
            if (st) st.textContent = "Online";
            setTimeout(warmOfflineCache, 1000);
        }
    }
    console.groupEnd();
});

// 8. Global Event Delegator (Maximum Robustness)
document.addEventListener('click', async (event) => {
    const target = event.target.closest('button, a, .status-dot');
    if (!target || !target.id) return;

    // Handle Queue Inspector Button (Navbar)
    if (target.id === QUEUE_BUTTON_ID) {
        console.log("[Offline UI] Global Delegate: Opening Inspector.");
        await openQueueInspector();
    }
    
    // Handle Queue Modal Buttons
    else if (target.id === 'queue-close-btn') {
        console.log("[Offline UI] Global Delegate: Closing Inspector.");
        closeQueueInspector();
    }
    else if (target.id === 'queue-refresh-btn') {
        console.log("[Offline UI] Global Delegate: Refreshing Inspector.");
        await openQueueInspector();
    }
    else if (target.id === 'queue-sync-btn') {
        console.log("[Offline UI] Global Delegate: Triggering Sync Now.");
        await triggerSync("admin_queue_modal");
    }
    else if (target.id === 'queue-retry-failed-btn') {
        console.log("[Offline UI] Global Delegate: Retrying failed actions.");
        try {
            const count = await db.actions.where("status").equals("failed").count();
            if (count > 0) {
                await db.actions.where("status").equals("failed").modify({ status: "pending" });
                console.log(`[Offline Sync] Reset ${count} failed actions.`);
                await updatePendingBadge();
                await openQueueInspector();
                if (typeof toastr !== 'undefined') toastr.success(`Reset ${count} failed actions.`);
            } else {
                console.log("[Offline Sync] No failed actions to retry.");
                if (typeof toastr !== 'undefined') toastr.info("No failed actions to retry.");
            }
        } catch (e) {
            console.error("[Offline Sync] Retry failed:", e);
        }
    }
    
    // Handle Offline Status Toggle (for debugging)
    else if (target.id === 'status-dot') {
        console.log("[Offline UI] Status dot clicked. Toggling...");
        const currentlyOffline = isOffline();
        window.ARC_OFFLINE(!currentlyOffline);
    }

    // Handle Logout Cache Clearing Logic
    else if (target.closest('a[href*="logout"]')) {
        console.log("[Offline UI] Logout detected. Cleaning up...");
        if ('serviceWorker' in navigator && navigator.serviceWorker.controller) {
            navigator.serviceWorker.controller.postMessage({ type: 'CLEAR_CACHE' });
        }
        sessionStorage.removeItem(LAST_STATE_KEY);
    }
});

console.log("[Arcadian Offline] Initialization sequence complete. Event delegation active.");
