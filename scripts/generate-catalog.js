const fs = require('fs');
const path = require('path');
const { logEvent } = require('../lib/logger');

const VAULT_DIR = 'C:\\Users\\Jinx\\Music\\Suno_DistroKid_Releases';
const PUBLIC_DIR = path.join(__dirname, '..', 'public');
const RELEASES_PUBLIC_DIR = path.join(PUBLIC_DIR, 'releases');
const CATALOG_JSON_PATH = path.join(PUBLIC_DIR, 'catalog.json');

function slugify(text) {
  return text
    .toLowerCase()
    .replace(/[^\w\s-]/g, '')
    .trim()
    .replace(/[\s_-]+/g, '-');
}

function cleanTitle(folderName) {
  // Strip trailing _hash if present
  return folderName.replace(/_[a-f0-9]{8}$/i, '').trim();
}

function extractHyperFollowUrl(txtContent, fallbackSlug) {
  if (!txtContent) return `https://distrokid.com/hyperfollow/jinx310/${fallbackSlug}`;
  const match = txtContent.match(/https?:\/\/(?:distrokid\.com\/hyperfollow|hyperfollow\.com)\/[^\s\)\"]+/i);
  return match ? match[0] : `https://distrokid.com/hyperfollow/jinx310/${fallbackSlug}`;
}

function generateCatalog() {
  logEvent('CATALOG', 'INFO', 'Starting metadata-to-card pipeline execution.');

  if (!fs.existsSync(VAULT_DIR)) {
    logEvent('CATALOG', 'ERROR', `DistroKid release vault path not found: ${VAULT_DIR}`);
    console.error(`[!] Directory not found: ${VAULT_DIR}`);
    return;
  }

  if (!fs.existsSync(RELEASES_PUBLIC_DIR)) {
    fs.mkdirSync(RELEASES_PUBLIC_DIR, { recursive: true });
  }

  // Load existing catalog if available to detect deltas
  let existingCatalog = [];
  if (fs.existsSync(CATALOG_JSON_PATH)) {
    try {
      existingCatalog = JSON.parse(fs.readFileSync(CATALOG_JSON_PATH, 'utf8'));
    } catch (e) {
      existingCatalog = [];
    }
  }
  const existingSlugs = new Set(existingCatalog.map(item => item.slug));

  const items = fs.readdirSync(VAULT_DIR, { withFileTypes: true });
  const releaseFolders = items.filter(item => item.isDirectory());

  const catalog = [];
  let newDeltaCount = 0;

  for (const dir of releaseFolders) {
    const rawFolderName = dir.name;
    const releasePath = path.join(VAULT_DIR, rawFolderName);
    const title = cleanTitle(rawFolderName);
    const slug = slugify(title);
    const targetDir = path.join(RELEASES_PUBLIC_DIR, slug);

    if (!fs.existsSync(targetDir)) {
      fs.mkdirSync(targetDir, { recursive: true });
    }

    const files = fs.readdirSync(releasePath);
    
    // Find cover image
    const coverFile = files.find(f => /\.(jpg|jpeg|png|webp)$/i.test(f));
    let coverUrl = '/assets/placeholder-cover.jpg';
    if (coverFile) {
      const coverSrc = path.join(releasePath, coverFile);
      const ext = path.extname(coverFile);
      const coverDest = path.join(targetDir, `cover${ext}`);
      fs.copyFileSync(coverSrc, coverDest);
      coverUrl = `/releases/${slug}/cover${ext}`;
    }

    // Find audio file
    const audioFile = files.find(f => /\.(mp3|wav|flac)$/i.test(f));
    let audioUrl = '';
    if (audioFile) {
      const audioSrc = path.join(releasePath, audioFile);
      const ext = path.extname(audioFile);
      const audioDest = path.join(targetDir, `audio${ext}`);
      // Copy preview if under 15MB to keep static bundle clean
      const stats = fs.statSync(audioSrc);
      if (stats.size <= 25 * 1024 * 1024) {
        fs.copyFileSync(audioSrc, audioDest);
        audioUrl = `/releases/${slug}/audio${ext}`;
      }
    }

    // Read metadata text prompt file if available
    let hyperfollowUrl = `https://distrokid.com/hyperfollow/jinx310/${slug}`;
    const txtFile = files.find(f => f.endsWith('.txt'));
    if (txtFile) {
      try {
        const txtContent = fs.readFileSync(path.join(releasePath, txtFile), 'utf8');
        hyperfollowUrl = extractHyperFollowUrl(txtContent, slug);
      } catch (e) {
        // Fallback used
      }
    }

    if (!existingSlugs.has(slug)) {
      newDeltaCount++;
    }

    catalog.push({
      id: slug,
      slug,
      title,
      artist: 'jinx3',
      producer: 'Guice Atkinson',
      coverUrl,
      audioUrl,
      hyperfollowUrl,
      shopifyProductId: '', // Placeholder for Shopify Buy Button integration
      hasAudio: Boolean(audioUrl),
      hasCover: Boolean(coverUrl !== '/assets/placeholder-cover.jpg')
    });
  }

  // Deduplicate catalog by slug
  const uniqueCatalogMap = new Map();
  for (const item of catalog) {
    if (!uniqueCatalogMap.has(item.slug)) {
      uniqueCatalogMap.set(item.slug, item);
    }
  }
  const finalCatalog = Array.from(uniqueCatalogMap.values());

  fs.writeFileSync(CATALOG_JSON_PATH, JSON.stringify(finalCatalog, null, 2), 'utf8');

  logEvent('CATALOG', 'INFO', `Catalog build complete. Total releases: ${finalCatalog.length}, New deltas: ${newDeltaCount}`, {
    totalReleases: finalCatalog.length,
    newDeltas: newDeltaCount,
    outputPath: CATALOG_JSON_PATH
  });

  console.log(`[+] Catalog generated with ${finalCatalog.length} releases (${newDeltaCount} new). Saved to catalog.json.`);
}

generateCatalog();
