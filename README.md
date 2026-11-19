# AI Shorts Maker Pro

GitHub-ready Streamlit app for creating vertical Shorts from a video URL or an uploaded file.

## What it does
- Uses Faster-Whisper speech recognition with word timestamps.
- Ranks candidate segments using transcript density, hook words, emphasis, and sentence completion.
- Exports 9:16 (1080x1920) H.264 MP4 clips.
- Burns animated karaoke-style captions (word-by-word highlight with a subtle scale animation).
- Offers individual MP4 downloads and one ZIP archive.

**Important:** Highlight ranking is AI-assisted and transcript-based, not a guarantee of virality. Review every clip before publishing. Face tracking, semantic LLM reasoning, and automatic YouTube publishing are not included in this version.

## Run locally
Install Python 3.11+, FFmpeg, then:

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy on Render
1. Create a GitHub repository named `ai-shorts-maker-pro`.
2. Upload the contents of this project (not the ZIP file itself).
3. In Render, choose **New + → Blueprint**.
4. Connect the GitHub repository. Render detects `render.yaml` and `Dockerfile`.
5. Deploy and open the generated Render URL.

GitHub Pages cannot run this app because it requires Python, FFmpeg, and CPU processing. GitHub stores the source; Render hosts the app.

## Hosting notes
- First use downloads a Whisper model; processing may be slow on a small CPU instance.
- Long videos need substantial RAM, CPU, disk space, and request time. The demo limits source duration to two hours.
- YouTube URL processing may fail for private, members-only, age-restricted, protected, region-restricted, or live-in-progress videos. Upload an authorized local file instead.
- Do not use this app to bypass access controls or copyright restrictions. Respect YouTube's terms and applicable law.
