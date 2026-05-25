from django import template
from django.contrib.admin.views.main import PAGE_VAR, ChangeList
from django.utils.html import format_html
from django.utils.safestring import SafeText

register = template.Library()


@register.simple_tag
def fixed_jazzmin_paginator_number(change_list: ChangeList, i: int) -> SafeText:
    """
    Generate an individual page index link in a paginated list.
    Fixed version of jazzmin_paginator_number for Django 6.0+
    """
    html_str = ""
    start = i == 1
    end = i == change_list.paginator.num_pages
    spacer = i in (".", "…")
    current_page = i == change_list.page_num

    if start:
        link = (
            change_list.get_query_string({PAGE_VAR: change_list.page_num - 1})
            if change_list.page_num > 1
            else "#"
        )
        disabled = "disabled" if link == "#" else ""
        html_str += format_html(
            """
            <li class="page-item previous {disabled}">
                <a class="page-link" href="{link}" data-dt-idx="0" tabindex="0">«</a>
            </li>
            """,
            disabled=disabled,
            link=link,
        )

    if current_page:
        html_str += format_html(
            """
            <li class="page-item active">
                <a class="page-link" href="javascript:void(0);" data-dt-idx="3" tabindex="0">{num}</a>
            </li>
            """,
            num=i,
        )
    elif spacer:
        html_str += """
        <li class="page-item">
            <a class="page-link" href="javascript:void(0);" data-dt-idx="3" tabindex="0">… </a>
        </li>
        """
    else:
        query_string = change_list.get_query_string({PAGE_VAR: i})
        end_class = "end" if end else ""
        html_str += format_html(
            """
            <li class="page-item">
                <a href="{query_string}" class="page-link {end_class}" data-dt-idx="3" tabindex="0">{num}</a>
            </li>
            """,
            num=i,
            query_string=query_string,
            end_class=end_class,
        )

    if end:
        link = (
            change_list.get_query_string({PAGE_VAR: change_list.page_num + 1})
            if change_list.page_num < i
            else "#"
        )
        disabled = "disabled" if link == "#" else ""
        html_str += format_html(
            """
            <li class="page-item next {disabled}">
                <a class="page-link" href="{link}" data-dt-idx="7" tabindex="0">»</a>
            </li>
            """,
            disabled=disabled,
            link=link,
        )

    from django.utils.safestring import mark_safe

    return mark_safe(html_str)
