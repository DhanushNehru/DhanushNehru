const fs = require('fs');
const path = require('path');

const API_KEY = process.env.YOUTUBE_API_KEY;
const CHANNEL_ID = 'UCkPSG_rUGJqAXmcajZ0mNMw'; // From your original URL
const README_PATH = path.join(__dirname, '../../README.md');

async function updateStats() {
    if (!API_KEY) {
        console.error('YOUTUBE_API_KEY is not set in the environment variables.');
        process.exit(1);
    }

    try {
        console.log(`Fetching stats for channel ${CHANNEL_ID}...`);
        const response = await fetch(`https://www.googleapis.com/youtube/v3/channels?part=statistics&id=${CHANNEL_ID}&key=${API_KEY}`);
        
        if (!response.ok) {
            throw new Error(`YouTube API returned ${response.status}: ${await response.text()}`);
        }
        
        const data = await response.json();

        if (!data.items || data.items.length === 0) {
            console.error('Could not find channel statistics.');
            process.exit(1);
        }

        const stats = data.items[0].statistics;
        const views = formatNumber(stats.viewCount);
        const subs = formatNumber(stats.subscriberCount);

        console.log(`Found ${views} views and ${subs} subscribers.`);

        let readmeContent = fs.readFileSync(README_PATH, 'utf-8');

        // Update Views
        const viewsRegex = /(<!-- YOUTUBE:VIEWS:START -->\n\s*)(.*)(\n\s*<!-- YOUTUBE:VIEWS:END -->)/;
        readmeContent = readmeContent.replace(viewsRegex, `$1<img src="https://img.shields.io/badge/Youtube%20Views-${views}-FF0000?style=for-the-badge&logo=youtube&logoColor=white" alt="Dhanush Nehru's YouTube Views"/>$3`);

        // Update Subscribers
        const subsRegex = /(<!-- YOUTUBE:SUBSCRIBERS:START -->\n\s*)(.*)(\n\s*<!-- YOUTUBE:SUBSCRIBERS:END -->)/;
        readmeContent = readmeContent.replace(subsRegex, `$1<img src="https://img.shields.io/badge/Youtube%20Subscribers-${subs}-FF0000?style=for-the-badge&logo=youtube&logoColor=white" alt="Dhanush Nehru's YouTube Subscribers"/>$3`);

        fs.writeFileSync(README_PATH, readmeContent);
        console.log('README.md updated successfully.');

    } catch (error) {
        console.error('Error fetching or updating stats:', error);
        process.exit(1);
    }
}

function formatNumber(numStr) {
    const num = parseInt(numStr, 10);
    if (num >= 1000000) {
        return (num / 1000000).toFixed(2).replace(/\.00$/, '') + 'M';
    }
    if (num >= 1000) {
        return (num / 1000).toFixed(2).replace(/\.00$/, '') + 'K';
    }
    return num.toString();
}

updateStats();
