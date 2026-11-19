import os, re, math, shutil, subprocess, tempfile, zipfile
from pathlib import Path
import streamlit as st
import yt_dlp
from faster_whisper import WhisperModel

st.set_page_config(page_title="AI Shorts Maker Pro", page_icon="🎬", layout="wide")
st.markdown("""
<style>
.stApp {background:linear-gradient(135deg,#090d1b 0%,#111a32 100%);color:#f4f6ff}
[data-testid="stSidebar"]{background:#10182b}
h1,h2,h3{color:#fff}
div.stButton>button{background:linear-gradient(90deg,#6d5dfc,#a855f7);color:white;border:0;border-radius:12px;font-weight:700;min-height:3rem}
div[data-testid="stDownloadButton"] button{border-radius:10px}
small,.muted{color:#a9b5d0}
</style>
""", unsafe_allow_html=True)

st.title("🎬 AI Shorts Maker Pro")
st.caption("Paste a video link or upload a file. AI finds highlight moments and creates vertical Shorts with animated captions.")
st.warning("Only process videos you own or have permission to edit. YouTube downloads can be restricted by privacy settings, copyright, region, or YouTube terms. For a reliable workflow, upload your authorized source video.")

with st.sidebar:
    st.header("⚙️ Shorts settings")
    n_clips = st.slider("Number of Shorts", 1, 10, 3)
    target_len = st.slider("Short length (seconds)", 15, 60, 35)
    min_gap = st.slider("Minimum gap between selected clips (seconds)", 0, 120, 20)
    whisper_size = st.selectbox("AI speech model", ["base", "small", "medium"], index=1)
    caption_lang = st.selectbox("Caption font", ["Auto / Bengali friendly", "English", "Bengali"], index=0)
    st.caption("The first run downloads the selected Whisper model. Medium is slower and needs more RAM.")

def run_cmd(args):
    p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode:
        raise RuntimeError((p.stderr or p.stdout)[-3000:])
    return p.stdout.strip()

def get_source(url, folder):
    out = folder / "source.%(ext)s"
    opts = {"outtmpl": str(out), "format": "bv*[height<=1080]+ba/b[height<=1080]/b",
            "merge_output_format":"mp4", "noplaylist":True, "quiet":True,
            "no_warnings":True, "retries":2, "fragment_retries":2}
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])
    files = [p for p in folder.glob("source.*") if p.suffix.lower() in [".mp4",".mkv",".webm",".mov"]]
    if not files:
        raise RuntimeError("Could not retrieve this URL. Upload your video file instead.")
    return max(files, key=lambda p:p.stat().st_size)

def probe_duration(path):
    return float(run_cmd(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",str(path)]))

def transcribe(path, model_name):
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segs, info = model.transcribe(str(path), vad_filter=True, word_timestamps=True,
                                  condition_on_previous_text=False)
    results=[]
    for s in segs:
        words=[]
        if s.words:
            for w in s.words:
                words.append({"start":float(w.start),"end":float(w.end),"word":w.word.strip()})
        results.append({"start":float(s.start),"end":float(s.end),"text":s.text.strip(),"words":words})
    return results, info.language

HOOKS = [
 "why","how","secret","mistake","never","best","worst","truth","finally","important",
 "amazing","unbelievable","problem","solution","tip","trick","wait","watch",
 "কেন","কীভাবে","গোপন","ভুল","সেরা","সবচেয়ে","সত্যি","অবিশ্বাস্য","দেখুন","জানেন","সমাধান","টিপস","অবশেষে"
]
EMOTION = ["!","?","wow","oh","আরে","বাহ","কিন্তু","তবে","কারণ","তাই","তাহলে"]

def score_window(start, end, segs):
    selected=[s for s in segs if s["start"] < end and s["end"] > start]
    text=" ".join(s["text"] for s in selected)
    if not text.strip(): return None
    words=re.findall(r"[\wঅ-৿]+", text.lower())
    if len(words)<10: return None
    duration=max(1,end-start)
    density=len(words)/duration
    low=text.lower()
    hook=sum(1 for h in HOOKS if h in low)
    emotion=sum(1 for e in EMOTION if e in low)
    # Favor a complete, speech-rich thought over sparse or overly dense sections.
    completeness=1.0 if text.rstrip().endswith((".", "!", "?", "।")) else 0.25
    length_fit=1.0-abs(duration-35)/70
    score=(density*1.8)+(hook*2.2)+(emotion*.45)+(completeness*1.1)+length_fit
    return {"start":start,"end":end,"text":text,"score":score}

def find_highlights(segs, duration, count, length, gap):
    # Candidate starts around sentence/segment boundaries, then rank by transcript signals.
    starts=set()
    for s in segs:
        starts.add(max(0.0, min(s["start"]-2.0, max(0,duration-length))))
        starts.add(max(0.0, min(s["start"], max(0,duration-length))))
    candidates=[]
    for start in starts:
        end=min(duration,start+length)
        c=score_window(start,end,segs)
        if c: candidates.append(c)
    candidates.sort(key=lambda x:x["score"], reverse=True)
    chosen=[]
    for c in candidates:
        if all(c["end"]+gap <= x["start"] or c["start"] >= x["end"]+gap for x in chosen):
            chosen.append(c)
        if len(chosen)>=count: break
    return sorted(chosen,key=lambda x:x["start"])

def ass_time(seconds):
    cs=max(0,int(round(seconds*100)))
    h=cs//360000; cs%=360000
    m=cs//6000; cs%=6000
    s=cs//100; cs%=100
    return f"{h}:{m:02}:{s:02}.{cs:02}"

def ass_escape(s):
    return s.replace("\\","\\\\").replace("{","\\{").replace("}","\\}").replace("\n"," ")

def make_animated_ass(segs, start, end, path, font):
    # Animated karaoke captions: each spoken word lights up and briefly scales.
    header=f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},66,&H00FFFFFF,&H0000D7FF,&H00101828,&H90000000,-1,0,0,0,100,100,0,0,1,5,2,2,75,75,190,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines=[header]
    for seg in segs:
        ws=[w for w in seg["words"] if w["end"]>start and w["start"]<end and w["word"]]
        if not ws:
            continue
        # Break into short readable lines (max 7 words).
        chunks=[ws[i:i+7] for i in range(0,len(ws),7)]
        for chunk in chunks:
            t0=max(start,chunk[0]["start"]); t1=min(end,chunk[-1]["end"])
            if t1<=t0: continue
            pieces=[]
            for w in chunk:
                a=max(t0,w["start"]); b=min(t1,w["end"])
                dur=max(1,int((b-a)*100))
                word=ass_escape(w["word"])
                # karaoke sweep + subtle pop animation on the active word
                pieces.append(r"{\k"+str(dur)+r"\fscx112\fscy112}"+word+r"{\fscx100\fscy100}")
            line=" ".join(pieces)
            lines.append(f"Dialogue: 0,{ass_time(t0-start)},{ass_time(t1-start)},Default,,0,0,0,,{line}\n")
    path.write_text("".join(lines),encoding="utf-8")

def render_short(source, clip, idx, outdir, segs, font):
    out=outdir/f"short_{idx:02}.mp4"
    ass=outdir/f"captions_{idx:02}.ass"
    make_animated_ass(segs,clip["start"],clip["end"],ass,font)
    ass_path=str(ass).replace("\\","/").replace(":","\\:")
    vf=f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,subtitles='{ass_path}'"
    run_cmd(["ffmpeg","-y","-ss",str(clip["start"]),"-i",str(source),"-t",str(clip["end"]-clip["start"]),
             "-vf",vf,"-r","30","-c:v","libx264","-preset","veryfast","-crf","22",
             "-c:a","aac","-b:a","160k","-movflags","+faststart",str(out)])
    return out

url=st.text_input("YouTube video / completed Live replay URL",placeholder="https://www.youtube.com/watch?v=...")
uploaded=st.file_uploader("Or upload an authorized video file",type=["mp4","mov","mkv","webm"])
if st.button("🚀 Find highlights & create Shorts",use_container_width=True):
    if not url.strip() and not uploaded:
        st.error("Paste a video URL or upload a video first.")
        st.stop()
    work=Path(tempfile.mkdtemp(prefix="ai_shorts_pro_"))
    try:
        with st.spinner("Preparing source video..."):
            if uploaded:
                source=work/Path(uploaded.name).name
                source.write_bytes(uploaded.getbuffer())
            else:
                source=get_source(url.strip(),work)
        duration=probe_duration(source)
        if duration>2*60*60:
            st.error("This hosted demo is limited to videos up to 2 hours. Try a shorter file.")
            st.stop()
        st.write(f"**Video duration:** {duration/60:.1f} minutes")
        with st.spinner("AI is transcribing speech and ranking highlight moments. This may take several minutes..."):
            segs,language=transcribe(source,whisper_size)
            clips=find_highlights(segs,duration,n_clips,target_len,min_gap)
        if not clips:
            st.error("No suitable speech-rich highlight was found. Try a video with clearer speech.")
            st.stop()
        st.success(f"Found {len(clips)} highlight candidates. Review the results before publishing.")
        font="Noto Sans Bengali" if caption_lang!="English" else "DejaVu Sans"
        outdir=work/"exports"; outdir.mkdir()
        progress=st.progress(0)
        rendered=[]
        for i,c in enumerate(clips,1):
            rendered.append(render_short(source,c,i,outdir,segs,font))
            progress.progress(i/len(clips))
        for i,(path,c) in enumerate(zip(rendered,clips),1):
            with st.expander(f"Short {i} · {int(c['start'])}s–{int(c['end'])}s · AI score {c['score']:.1f}",expanded=True):
                st.video(str(path))
                st.caption(c["text"][:650])
                st.download_button("⬇️ Download MP4",path.read_bytes(),file_name=path.name,mime="video/mp4",key=f"clip{i}")
        archive=work/"ai_shorts_export.zip"
        with zipfile.ZipFile(archive,"w",zipfile.ZIP_DEFLATED) as z:
            for p in rendered:z.write(p,p.name)
        st.download_button("📦 Download all Shorts (ZIP)",archive.read_bytes(),file_name="ai_shorts_export.zip",mime="application/zip")
        st.caption(f"Speech language detected: {language}. Captions are generated from speech recognition; please check names and wording before publishing.")
    except Exception as e:
        st.error(f"Processing failed: {e}")
        st.info("If a YouTube URL fails, try uploading the original MP4. Some live streams cannot be processed until a replay is available.")
    finally:
        shutil.rmtree(work,ignore_errors=True)
