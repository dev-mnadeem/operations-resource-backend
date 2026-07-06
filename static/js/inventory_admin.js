(function($) {
    'use strict';
    $(function() {
        var $categoryField = $('#id_category');
        var $subCategoryField = $('#id_sub_category');
        
        // Store all original options
        var $allOptions = $subCategoryField.find('option').clone();

        function filterSubCategories(categoryId) {
            var selectedSubCategoryId = $subCategoryField.val();
            
            // Clear current options
            $subCategoryField.empty();
            
            // Add the default empty option
            var $placeholder = $allOptions.filter('[value=""]').first().clone();
            $subCategoryField.append($placeholder);

            if (!categoryId) {
                return;
            }

            // Add filtered options
            $allOptions.each(function() {
                var $option = $(this);
                if ($option.attr('data-parent-id') == categoryId) {
                    var $newOption = $option.clone();
                    if ($newOption.val() == selectedSubCategoryId) {
                        $newOption.attr('selected', 'selected');
                    }
                    $subCategoryField.append($newOption);
                }
            });
        }

        $categoryField.on('change', function() {
            filterSubCategories($(this).val());
        });

        // Initialize on page load
        var initialCategoryId = $categoryField.val();
        if (initialCategoryId) {
            filterSubCategories(initialCategoryId);
        }
    });
})(django.jQuery);
