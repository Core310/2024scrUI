$(document).keydown(function (e) {

    const activeLink = document.querySelector('a.nav-link.active');

    let newActiveLink;
    switch (e.which) {
        case 37: // left
            i === dataPageIds.length ? i = 0 : i++;//TODO 5/11/2024 Get the current navigation to take into account the current index of whatever tab ur currently on


            const activeNav = $('.nav-link.active'); //grabs all elements with .nav-link.active classes
            activeNav.removeClass('active');//Disable current tab
            const oldPageId = activeNav.attr('data-page-id'); //Current page id
            $('#' + oldPageId).hide(); //hide old page with IDD

            const pageId = $(`.nav-link[data-page-id="${dataPageIds[i]}"]`); //new page ID to be shown where (this) is the clicked element
            pageId.addClass('active');//make clicked element active

            $('#' + pageId).show();


            //new code above

            break;
        case 39: // right
            newActiveLink = activeLink.parentElement.nextElementSibling?.querySelector('a.nav-link.active');
            break;
        default:
            return;
    }
    e.preventDefault();
});

// These are the page IDs that are used to navigate through the tabs (basically tab names)
const dataPageIds = [
    "dashboard",
    "vision",
    "logging",
    "configuration",
    "conbus",
    "preferences",
    "debug"
];
let i = 0;
