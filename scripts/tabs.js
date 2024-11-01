$(document).ready(function () {
    $('.page').hide();
    $('.page:first').show();

    // When any a tag with a class of nav-link is clicked, get the corresponding div of page with data-page-id attribute and show it
    $('.nav-link').on('click', function () {
        const activeNav = $('.nav-link.active');
        activeNav.removeClass('active');
        const oldPageId = activeNav.attr('data-page-id');
        $('#' + oldPageId).hide();

        $(this).addClass('active');

        const pageId = $(this).attr('data-page-id');
        $('#' + pageId).show();
    });
})