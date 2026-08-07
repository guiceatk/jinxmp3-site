# DistroKid metadata (form is source of truth)

## Critical rule
DistroKid **ignores embedded audio tags** (ID3/iXML/etc.).  
Everything that reaches Spotify/Apple is what you type on the **web form**.  
Local `metadata.json` / `metadata.md` are **copy-paste aids**, not auto-upload.

## Audio
- Formats: WAV (preferred), MP3, M4A, FLAC, AIFF, WMA  
- Filename: correct extension; **no** `\ / : * ? " < > |`  
- Max size ~1 GB/track  
- Track length limits apply; albums: avoid avg track length under ~60s  

## Artwork
- **JPG only**, RGB, single flat image  
- Min 1000×1000; **ideal 3000×3000 square**  

## Release-level (form)
- Single / EP / Album  
- Release title, primary artist (consistent spelling)  
- Release date (often future)  
- **UPC**: DistroKid generates (do not invent)  
- Genre / subgenre, explicit flag  

## Track-level (form)
- Track title (exact spelling)  
- Primary artist; collabs: names with `&`/`and` + collaboration type  
- **Songwriter real/legal names** (publishing)  
- **ISRC**: DistroKid free generation (default) OR paste own if registered  
- Explicit yes/no; radio edit flags; optional lyrics  
- Credits: Producer, Guitar, Composer, etc.  

## ISRC policy (jinx3 workflow)
1. Default: leave blank → DistroKid assigns  
2. After upload: copy ISRC from DistroKid dashboard into local registry  
3. Optional later: own registrant code + higher DistroKid plan to import  

## jinx3 defaults
- Stage artist: **jinx3**  
- Guitar: **Guice Atkinson**  
- Producer: **Guice Atkinson**  
- Songwriter: use real legal name on form when required (not only stage name)  
