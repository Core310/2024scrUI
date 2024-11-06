$(document).keydown(function (e) {
    let LETFTKEY = 37,
        RIGHTKEY = 39;

    const activeLink = document.querySelector('a.nav-link.active');

    let newActiveLink;
    switch (e.which) {
        case LETFTKEY:
            i = currentPageIndex();
            i === dataPageIds.length - 1 ? i = 0 : i++;//i===lastPage? 0 : ++

            const activeNav = $('.nav-link.active'); //grabs all elements with .nav-link.active classes
            activeNav.removeClass('active');//Disable current tab from active tab list
            const oldPageId = activeNav.attr('data-page-id'); //Current page id
            $('#' + oldPageId).hide(); //hide old page


            const pageId = $(`.nav-link[data-page-id="${dataPageIds[i]}"]`); //new page ID to navigated to
            pageId.addClass('active');//make selected dataPage active fixme this line should be before the bind?
            $('#' + $(`.nav-link.active`).attr('data-page-id')).show();//show the current page fixme!! not showing the page after hiding prev page

            break;
        case RIGHTKEY:
            //TODO 5/11/2024 once done with above put that here
            break;
        default:
            return;
    }
    e.preventDefault();
});

function currentPageIndex() {
    let currentPageId = $('.nav-link.active').attr('data-page-id');
    for (let i = 0; i < dataPageIds.length; i++) {
        if (dataPageIds[i] === currentPageId) {
            return i;
        }
    }
    console.log(`No page found with id ${currentPageId} likely problem with never updating the page index`);
    throw new Error(`No page found with id ${currentPageId}`);
}

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
let i = -1;
