from django import forms
from django.contrib.auth.models import Permission
from django.utils.safestring import mark_safe


class PermissionGridWidget(forms.CheckboxSelectMultiple):
    def render(self, name, value, _attrs=None, _renderer=None):
        if value is None:
            value = []

        selected_pks = [str(v) for v in value]
        apps = {}

        for pk, _label in self.choices:
            try:
                perm_id = pk.value if hasattr(pk, "value") else pk
                perm = Permission.objects.select_related("content_type").get(pk=perm_id)
                app_label = perm.content_type.app_label
                model_name = perm.content_type.model
                codename = perm.codename

                action = "other"
                if codename.startswith("add_"):
                    action = "add"
                elif codename.startswith("change_"):
                    action = "change"
                elif codename.startswith("delete_"):
                    action = "delete"
                elif codename.startswith("view_"):
                    action = "view"

                if app_label not in apps:
                    apps[app_label] = {}
                if model_name not in apps[app_label]:
                    apps[app_label][model_name] = {
                        "add": None,
                        "change": None,
                        "delete": None,
                        "view": None,
                        "other": [],
                    }

                if action == "other":
                    apps[app_label][model_name]["other"].append((perm_id, perm.name))
                else:
                    apps[app_label][model_name][action] = (perm_id, perm.name)
            except Exception:
                continue

        if not apps:
            return mark_safe(
                "<p style='color: #94a3b8; font-style: italic; padding: 20px; text-align: center;'>No permissions available.</p>"
            )

        html = [
            '<div class="perm-jazz-v4">',
            "<style>",
            '  .perm-jazz-v4 { font-family: "Source Sans Pro", -apple-system, sans-serif; font-size: 13px; color: #333; }',
            "  .p-table { width: 100%; border-collapse: collapse; margin-bottom: 25px; background: #fff; border: 1px solid #dee2e6; }",
            "  .p-table th, .p-table td { border: 1px solid #ebeef5; padding: 10px 12px; text-align: center; vertical-align: top; }",
            "  .p-table .app-banner { background: #417690; color: #fff; text-align: left; padding: 10px 15px; font-weight: 600; font-size: 14px; border: none; }",
            "  .p-table .label-col { text-align: left; background: #fdfdfd; width: 35%; border-right: 1px solid #eee; }",
            "  .p-table .action-col { width: 12%; background: #fbfbfc; border-left: 1px solid #eee; }",
            "  .p-table .perm-name { font-weight: 600; color: #333; display: block; margin-bottom: 4px; text-transform: capitalize; font-size: 13px; }",
            "  .p-table .hdr { font-size: 11px; text-transform: uppercase; color: #888; background: #fbfbfc; font-weight: 700; height: 35px; }",
            "  .p-table .toggle-row { background: #fafafa; border-top: 1px solid #eee; }",
            "  .p-table .toggle-row th { font-size: 11px; text-transform: uppercase; color: #888; background: #fafafa; font-weight: 700; height: 35px; }",
            "  .btn-p { color: #417690; cursor: pointer; font-size: 11px; font-weight: 600; padding: 1px 6px; border-radius: 3px; border: 1px solid #ddd; background: #fff; transition: all 0.2s; }",
            "  .btn-p:hover { background: #f4f4f4; border-color: #ccc; }",
            "  .btn-banner { color: #fff; border-color: rgba(255,255,255,0.3); background: transparent; }",
            "  .btn-banner:hover { background: rgba(255,255,255,0.1); color: #fff; border-color: #fff; }",
            "  .other-box { margin-top: 8px; padding-top: 6px; border-top: 1px dashed #eee; }",
            "  .other-label { display: block; font-size: 11px; color: #666; margin-bottom: 3px; cursor: pointer; }",
            "  .p-chk { cursor: pointer; width: 15px; height: 15px; accent-color: #417690; vertical-align: middle; margin: 0; }",
            "  .p-table tr:hover td { background-color: #f9fafb !important; }",
            "  .app-banner { cursor: pointer; user-select: none; position: relative; }",
            "  .collapse-icon { display: inline-block; transition: transform 0.2s; margin-right: 8px; font-size: 10px; vertical-align: middle; }",
            "  .p-table.is-collapsed .collapse-icon { transform: rotate(-90deg); }",
            "  .p-table.is-collapsed thead tr:not(:first-child), .p-table.is-collapsed tbody { display: none; }",
            "</style>",
            "<script>",
            '  function toggleSection(el) { el.closest(".p-table").classList.toggle("is-collapsed"); }',
            '  function setApp(ap, v) { document.querySelectorAll(".ap-"+ap).forEach(c => c.checked = v); }',
            '  function tgRow(m, ap, mo) { document.querySelectorAll(".ap-"+ap+".mo-"+mo).forEach(c => c.checked = m.checked); }',
            '  function tgCol(m, ap, ac) { document.querySelectorAll(".ap-"+ap+".ac-"+ac).forEach(c => c.checked = m.checked); }',
            "</script>",
        ]

        for idx, (app_label, models) in enumerate(sorted(apps.items())):
            collapse_class = "" if idx == 0 else "is-collapsed"
            html.append(f'<table class="p-table {collapse_class}">')
            html.append("  <thead>")
            html.append("    <tr>")
            html.append(
                '      <th colspan="6" class="app-banner" onclick="toggleSection(this)">'
            )
            html.append('        <span class="collapse-icon">▼</span>')
            html.append(f"        <span>{app_label.upper()}</span>")
            html.append("      </th>")
            html.append("    </tr>")
            html.append('    <tr class="hdr">')
            html.append('      <th style="text-align:left">Permissions</th>')
            for action in ["view", "add", "change", "delete"]:
                html.append(f"      <th>{action.capitalize()}</th>")
            html.append('      <th class="action-col">Select All</th>')
            html.append("    </tr>")

            # Check if EVERYTHING in this app is checked for the global master
            app_pks = []
            for _m_name, m_perms in models.items():
                for action in ["view", "add", "change", "delete"]:
                    if m_perms[action]:
                        app_pks.append(str(m_perms[action][0]))
                for p_id, _ in m_perms["other"]:
                    app_pks.append(str(p_id))

            app_checked = (
                all(apk in selected_pks for apk in app_pks) if app_pks else False
            )
            app_checked_attr = "checked" if app_checked else ""

            html.append('    <tr class="toggle-row">')
            html.append('      <th style="text-align:left">Select All</th>')
            for action in ["view", "add", "change", "delete"]:
                col_pks = []
                for _m_name, m_perms in models.items():
                    if m_perms[action]:
                        col_pks.append(str(m_perms[action][0]))
                col_checked = (
                    all(cpk in selected_pks for cpk in col_pks) if col_pks else False
                )
                col_checked_attr = "checked" if col_checked else ""
                html.append("      <th>")
                html.append(
                    f'        <input type="checkbox" class="p-chk ap-{app_label}" onclick="tgCol(this, \'{app_label}\', \'{action}\')" {col_checked_attr}>'
                )
                html.append("      </th>")
            html.append(
                '      <th class="action-col" title="Toggle entire application">'
            )
            html.append(
                f'        <input type="checkbox" class="p-chk" onclick="setApp(\'{app_label}\', this.checked)" {app_checked_attr}>'
            )
            html.append("      </th>")
            html.append("    </tr>")
            html.append("  </thead>")
            html.append("  <tbody>")

            for model_name, perms in sorted(models.items()):
                row_ids = []
                for action in ["view", "add", "change", "delete"]:
                    if perms[action]:
                        row_ids.append(str(perms[action][0]))
                for p_id, _ in perms["other"]:
                    row_ids.append(str(p_id))
                all_checked = (
                    all(rid in selected_pks for rid in row_ids) if row_ids else False
                )
                checked_attr = "checked" if all_checked else ""

                html.append("    <tr>")
                html.append('      <td class="label-col">')
                html.append(
                    f'        <span class="perm-name">{model_name.replace("_", " ")}</span>'
                )
                if perms["other"]:
                    html.append('        <div class="other-box">')
                    for p_id, p_name in perms["other"]:
                        checked = "checked" if str(p_id) in selected_pks else ""
                        html.append(
                            f'          <label class="other-label" title="{p_name}">'
                        )
                        html.append(
                            f'            <input type="checkbox" name="{name}" value="{p_id}" class="p-chk ap-{app_label} mo-{model_name} ac-other" {checked}> {p_name}'
                        )
                        html.append("          </label>")
                    html.append("        </div>")
                html.append("      </td>")

                for action in ["view", "add", "change", "delete"]:
                    val = perms[action]
                    html.append("      <td>")
                    if val:
                        perm_id = val[0]
                        checked = "checked" if str(perm_id) in selected_pks else ""
                        html.append(
                            f'        <input type="checkbox" name="{name}" value="{perm_id}" class="p-chk ap-{app_label} mo-{model_name} ac-{action}" {checked}>'
                        )
                    else:
                        html.append('        <span style="color:#e2e8f0">-</span>')
                    html.append("      </td>")

                html.append('      <td class="action-col">')
                html.append(
                    f'        <input type="checkbox" class="p-chk ap-{app_label}" onclick="tgRow(this, \'{app_label}\', \'{model_name}\')" {checked_attr}>'
                )
                html.append("      </td>")
                html.append("    </tr>")

        html.append("  </tbody>")
        html.append("</table>")
        html.append("</div>")
        return mark_safe("\n".join(html))
