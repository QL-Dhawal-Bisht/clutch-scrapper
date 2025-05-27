// ==UserScript==
// @name         Clutch-scrapper
// @namespace    https://clutch.co
// @version      2.4
// @description  Visit each company profile, scrape all paginated reviews, log to console, and export data as CSV
// @match        https://clutch.co/*
// @grant        none
// ==/UserScript==

(function () {
    const delay = ms => new Promise(res => setTimeout(res, ms));

    function downloadAsCSV(filename, rows) {
        // Correct headers with swapped names only
        const header = ['Reviewer Company', 'Reviewer Name', 'Location', 'Company Size', 'Review Type'];

        const csvContent = [
            header.join(','), // Swapped headers
            ...rows.map(r => [
                r.reviewerName,
                r.reviewerCompany,
                r.reviewerLocation,
                r.reviewerCompanySize,
                r.reviewType
            ].map(v => `"${v.replace(/"/g, '""')}"`).join(','))
        ].join('\n');

        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    }

    function getCurrentHash() {
        const blocks = document.querySelectorAll('#reviews-sg-accordion [id^="review-"]');
        let combined = '';
        blocks.forEach(b => combined += b.innerText.trim());
        return btoa(unescape(encodeURIComponent(combined.slice(0, 1000))));
    }

    async function scrapeAllReviewPages() {
        let allReviews = [];
        let currentPage = 1;
        const seenHashes = new Set();

        const reviewContainerSelector = '#reviews-sg-accordion';
        const maxPagesEl = document.querySelector('.sg-pagination__link--icon-last');
        const maxPages = parseInt(maxPagesEl?.dataset?.page || '1');

        console.log(`🔍 Total review pages: ${maxPages}`);

        while (true) {
            await delay(1500);

            const reviewBlocks = document.querySelectorAll(`${reviewContainerSelector} [id^="review-"]`);
            const pageHash = getCurrentHash();

            if (seenHashes.has(pageHash)) {
                console.warn("⚠️ Duplicate page detected, stopping.");
                break;
            }

            seenHashes.add(pageHash);

            if (currentPage === 1) {
                const reviewSection = document.querySelector(reviewContainerSelector);
                if (reviewSection) {
                    reviewSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    await delay(1500); // Allow lazy-load
                }
            }

            console.log(`📄 Scraping page ${currentPage} of ~${maxPages}...`);

            reviewBlocks.forEach((block, i) => {
                const reviewerSection = block.querySelector('.profile-review__reviewer.mobile_hide');
                if (!reviewerSection) return;

                const lines = reviewerSection.innerText
                    .split('\n')
                    .map(line => line.trim())
                    .filter(Boolean);

                const review = {
                    reviewerName: lines[0] || 'N/A',
                    reviewerCompany: lines[1] || 'N/A',
                    reviewerLocation: lines[3] || 'N/A',
                    reviewerCompanySize: lines[4] || 'N/A',
                    reviewType: lines[5] || 'N/A',
                };

                allReviews.push(review);
                console.log(`✅ Review ${allReviews.length}:`, review);
            });

            const nextBtn = document.querySelector('.sg-pagination__link--icon-next');
            if (!nextBtn || nextBtn.disabled || currentPage >= maxPages) {
                console.log('⛔ No more pages to scrape.');
                break;
            }

            currentPage++;
            nextBtn.click();
            await delay(3000); // Wait for new page to load
        }

        console.log(`🎯 Total reviews scraped: ${allReviews.length}`);
        return allReviews;
    }

    async function handleDirectoryPage() {
        const profileLinks = [...document.querySelectorAll('a.provider__cta-link.directory_profile')];
        if (!profileLinks.length) return;

        const urls = profileLinks.map(a => a.href);
        localStorage.setItem('clutch_company_urls', JSON.stringify(urls));
        localStorage.setItem('clutch_company_index', '0');
        console.log(`✅ Stored ${urls.length} company profile URLs.`);
        window.location.href = urls[0];
    }

    async function handleProfilePage() {
        const urls = JSON.parse(localStorage.getItem('clutch_company_urls') || '[]');
        let index = parseInt(localStorage.getItem('clutch_company_index') || '0');

        if (!urls.length || index >= urls.length) {
            console.log('✅ Done visiting all profiles.');
            localStorage.removeItem('clutch_company_urls');
            localStorage.removeItem('clutch_company_index');
            return;
        }

        console.log(`🏢 Visiting company ${index + 1} of ${urls.length}: ${window.location.href}`);

        const allReviews = await scrapeAllReviewPages();

        const companyName = document.querySelector('h1')?.innerText?.trim().replace(/[\\/:*?"<>|]/g, '_') || `company_${index + 1}`;
        console.log(`💾 Saving reviews for: ${companyName}`);
        downloadAsCSV(`${companyName}_reviews.csv`, allReviews);

        index++;
        localStorage.setItem('clutch_company_index', index.toString());

        if (index < urls.length) {
            console.log('⏭️ Moving to next profile...');
            await delay(2000);
            window.location.href = urls[index];
        } else {
            console.log('🎉 Finished visiting all company profiles.');
            localStorage.removeItem('clutch_company_urls');
            localStorage.removeItem('clutch_company_index');
        }
    }

    const isDirectoryPage = document.querySelectorAll('a.provider__cta-link.directory_profile').length > 0;

    if (isDirectoryPage) {
        console.log('📂 On directory page. Extracting company URLs...');
        handleDirectoryPage();
    } else {
        console.log('📑 On profile page. Scraping reviews...');
        handleProfilePage();
    }
})();