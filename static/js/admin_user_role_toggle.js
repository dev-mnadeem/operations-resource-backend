(function () {
  "use strict";

  const ROLE_FIELDS = {
    Admin: { hide: ["branch", "purchaser_branches", "warehouse"] },
    "Warehouse Manager": { hide: ["branch", "purchaser_branches"], show: ["warehouse"] },
    Purchaser: { hide: ["branch", "warehouse"], show: ["purchaser_branches"] },
    _default: { show: ["branch"], hide: ["warehouse", "purchaser_branches"] },
  };

  function getRow(fieldName) {
    const el =
      document.getElementById("id_" + fieldName) ||
      document.querySelector('[name="' + fieldName + '"]');
    if (!el) return null;
    return el.closest(".form-row") || el.closest("fieldset > div") || el.parentElement;
  }

  function applyVisibility(groupName) {
    const rule = ROLE_FIELDS[groupName] || ROLE_FIELDS._default;
    const allFields = ["branch", "purchaser_branches", "warehouse"];

    allFields.forEach(function (field) {
      const row = getRow(field);
      if (!row) return;
      const shouldHide = (rule.hide || []).includes(field);
      row.style.display = shouldHide ? "none" : "";
    });
  }

  function init() {
    const select = document.getElementById("id_role_group");
    if (!select) return;

    const selectedText =
      select.options[select.selectedIndex] && select.options[select.selectedIndex].text;
    applyVisibility(selectedText || "");

    select.addEventListener("change", function () {
      const text = this.options[this.selectedIndex]
        ? this.options[this.selectedIndex].text
        : "";
      applyVisibility(text);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
