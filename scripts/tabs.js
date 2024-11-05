$(document).ready(function () {
    $('.page').hide();
    $('.page:first').show();

    // When any a tag with a class of nav-link is clicked, get the corresponding div of page with data-page-id attribute and show it
    $('.nav-link').on('click', function () {
        const activeNav = $('.nav-link.active'); //grabs all elements with .nav-link.active classes
        activeNav.removeClass('active');//Disable current tab
        const oldPageId = activeNav.attr('data-page-id'); //Current page id
        $('#' + oldPageId).hide(); //hide old page with IDD

        $(this).addClass('active');//make clicked element active

        const pageId = $(this).attr('data-page-id'); //new page ID to be shown where (this) is the clicked element
        $('#' + pageId).show();
    });
})