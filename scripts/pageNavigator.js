$(document).keydown(function (e) {
    const activeLink = document.querySelector('a.nav-link.active');
    let newActiveLink;

    switch (e.which) {
        case 37: // left
            i === dataPageIds.length ? i = 0 : i++;
            const activeNav = $('.nav-link.active');
            activeNav.removeClass('active');
            const oldPageId = activeNav.attr('data-page-id');
            $('#' + oldPageId).hide();
            const pageId = dataPageIds[i];
            $('#' + pageId).show();
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
