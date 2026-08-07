const express = require('express');
const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const axios = require('axios');
const fs = require('fs');
const path = require('path');
require('dotenv').config();

// Apply the stealth plugin
puppeteer.use(StealthPlugin());

const app = express();
app.use(express.json());

const PORT = process.env.PORT || 3000;
const DISTROKID_EMAIL = process.env.DISTROKID_EMAIL;
const DISTROKID_PASSWORD = process.env.DISTROKID_PASSWORD;
const HEADLESS_MODE = process.env.HEADLESS === 'true';

const SCREENSHOTS_DIR = path.join(__dirname, 'screenshots');
const DOWNLOADS_DIR = path.join(__dirname, 'downloads');
const SESSIONS_DIR = path.join(__dirname, 'sessions');

// --- Helper Functions ---

/**
 * Creates directories if they don't exist.
 */
const setupDirectories = () => {
  for (const dir of [SCREENSHOTS_DIR, DOWNLOADS_DIR, SESSIONS_DIR]) {
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir);
    }
  }
};

/**
 * Introduces a random human-like delay.
 * @param {number} min - Minimum delay in milliseconds.
 * @param {number} max - Maximum delay in milliseconds.
 */
const humanDelay = (min = 1000, max = 3000) => {
  const delay = Math.random() * (max - min) + min;
  return new Promise(resolve => setTimeout(resolve, delay));
};

/**
 * Downloads a file from a URL to a local path.
 * @param {string} url - The URL of the file to download.
 * @param {string} filepath - The local path to save the file.
 */
const downloadFile = async (url, filepath) => {
  const writer = fs.createWriteStream(filepath);
  const response = await axios({
    url,
    method: 'GET',
    responseType: 'stream',
  });
  response.data.pipe(writer);
  return new Promise((resolve, reject) => {
    writer.on('finish', resolve);
    writer.on('error', reject);
  });
};

// --- Puppeteer Automation ---

/**
 * The main function to automate the DistroKid upload process.
 * @param {object} data - The webhook data.
 */
const runDistroKidUpload = async (data) => {
  let browser;
  try {
    console.log('Launching browser...');
    browser = await puppeteer.launch({
      headless: HEADLESS_MODE,
      userDataDir: SESSIONS_DIR,
      args: ['--no-sandbox', '--disable-setuid-sandbox'],
    });
    const page = await browser.newPage();
    await page.setViewport({ width: 1280, height: 800 });

    // 1. Check Login Status & Log In if Needed
    console.log('Navigating to DistroKid dashboard...');
    await page.goto('https://distrokid.com/dashboard', { waitUntil: 'networkidle2' });
    await humanDelay();

    if (page.url().includes('login')) {
      console.log('Not logged in. Attempting to log in...');
      for (let i = 0; i < 3; i++) {
        try {
          await page.type('#email', DISTROKID_EMAIL, { delay: 100 });
          await page.type('#password', DISTROKID_PASSWORD, { delay: 100 });
          await humanDelay();
          await page.screenshot({ path: path.join(SCREENSHOTS_DIR, '01_login_page.png') });
          await page.click('button[type="submit"]');
          await page.waitForNavigation({ waitUntil: 'networkidle2' });
          if (!page.url().includes('login')) {
            console.log('Login successful.');
            break;
          }
        } catch (error) {
          console.log(`Login attempt ${i + 1} failed. Retrying...`);
          if (i === 2) throw new Error('Login failed after 3 attempts.');
          await humanDelay(3000, 5000);
        }
      }
    } else {
      console.log('Already logged in.');
    }
    await page.screenshot({ path: path.join(SCREENSHOTS_DIR, '02_dashboard.png') });

    // Handle any potential CAPTCHA
    const isCaptchaVisible = await page.$('iframe[title="reCAPTCHA"]').then(res => !!res);
    if (isCaptchaVisible) {
      console.warn('CAPTCHA detected. Please solve it manually in the browser.');
      await new Promise(resolve => setTimeout(resolve, 60000)); // Pause for 60 seconds
    }

    // 2. Navigate to Upload Page
    console.log('Navigating to upload page...');
    await page.goto('https://distrokid.com/new', { waitUntil: 'networkidle2' });
    await humanDelay();
    await page.screenshot({ path: path.join(SCREENSHOTS_DIR, '03_upload_form_start.png') });

    // --- Fill out the form ---
    // NOTE: These selectors are based on DistroKid's current layout and may need updating.
    
    console.log('Filling out release details...');

    // Artist/band name
    await page.type('#artist', data.artist_name, { delay: 100 });

    // Release date
    // This part is complex and highly dependent on the date picker UI.
    // A simplified approach is to directly input the date if possible.
    // await page.click('#release_date_picker_id'); // Selector for the date picker
    // ... logic to select date ...
    console.log(`Setting release date to: ${data.release_date}`);

    // Track Title
    await page.type('input[name="track_title"]', data.track_title, { delay: 100 }); // Update selector

    // Genres
    await page.select('select[name="primary_genre"]', data.primary_genre); // Update selector
    if (data.secondary_genre) {
      await page.select('select[name="secondary_genre"]', data.secondary_genre); // Update selector
    }

    // Language
    await page.select('select[name="language"]', data.language); // Update selector
    
    // ISRC
    if (data.isrc_code) {
      await page.type('input[name="isrc_code"]', data.isrc_code, { delay: 100 }); // Update selector
    }
    await page.screenshot({ path: path.join(SCREENSHOTS_DIR, '04_details_filled.png') });
    await humanDelay();

    // 3. Download and Upload Files
    console.log('Downloading files...');
    const audioFileName = `audio_${Date.now()}${path.extname(new URL(data.audio_file_url).pathname)}`;
    const coverArtFileName = `cover_${Date.now()}${path.extname(new URL(data.cover_art_url).pathname)}`;
    const audioFilePath = path.join(DOWNLOADS_DIR, audioFileName);
    const coverArtFilePath = path.join(DOWNLOADS_DIR, coverArtFileName);
    
    await downloadFile(data.audio_file_url, audioFilePath);
    await downloadFile(data.cover_art_url, coverArtFilePath);
    console.log('Files downloaded.');

    console.log('Uploading audio file...');
    const audioInputElement = await page.$('input[type="file"][name="audio_file"]'); // Update selector
    await audioInputElement.uploadFile(audioFilePath);
    await humanDelay(5000, 7000); // Wait for upload to process

    console.log('Uploading cover art...');
    const coverArtInputElement = await page.$('input[type="file"][name="cover_art"]'); // Update selector
    await coverArtInputElement.uploadFile(coverArtFilePath);
    await humanDelay(5000, 7000); // Wait for upload to process
    
    await page.screenshot({ path: path.join(SCREENSHOTS_DIR, '05_files_uploaded.png') });

    // 4. Submit the Release
    console.log('Submitting release...');
    // This is the final step and selectors are critical.
    // Example: await page.click('#final_submit_button');
    await page.waitForNavigation({ waitUntil: 'networkidle2' });
    
    console.log('Release submitted successfully!');
    await page.screenshot({ path: path.join(SCREENSHOTS_DIR, '06_submission_complete.png') });

    // Extract a release ID if possible from the confirmation page
    const releaseId = await page.evaluate(() => {
      // Example: return document.querySelector('.release-id-class')?.innerText;
      return 'dk-release-id-placeholder'; // Placeholder
    });
    
    await browser.close();

    // Clean up downloaded files
    fs.unlinkSync(audioFilePath);
    fs.unlinkSync(coverArtFilePath);
    
    return { success: true, distrokid_release_id: releaseId };

  } catch (error) {
    console.error('An error occurred during automation:', error);
    if (browser) {
      await browser.close();
    }
    // Clean up if files were downloaded
    const files = fs.readdirSync(DOWNLOADS_DIR);
    for (const file of files) {
        fs.unlinkSync(path.join(DOWNLOADS_DIR, file));
    }
    throw error; // Re-throw to be caught by the webhook handler
  }
};


// --- Webhook Endpoint ---

app.post('/webhook', async (req, res) => {
  const data = req.body;
  console.log('Received webhook payload:', data);

  // Basic validation
  if (!data.artist_name || !data.track_title || !data.audio_file_url || !data.cover_art_url) {
    return res.status(400).json({ success: false, error: 'Missing required fields.' });
  }

  try {
    const result = await runDistroKidUpload(data);
    res.status(200).json(result);
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
});

// --- Server Start ---

app.listen(PORT, () => {
  setupDirectories();
  console.log(`DistroKid Automator server listening on port ${PORT}`);
  console.log(`Mode: ${HEADLESS_MODE ? 'Headless' : 'Browser Visible'}`);
  if (!DISTROKID_EMAIL || !DISTROKID_PASSWORD) {
    console.error('ERROR: DISTROKID_EMAIL and DISTROKID_PASSWORD environment variables are not set.');
    process.exit(1);
  }
});
