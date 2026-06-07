import os, re, subprocess
from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client
load_dotenv()
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
CHANNEL_URL = os.environ["CHANNEL_URL"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
openai_client = OpenAI(api_key="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")

def get_video_ids(channel_url):
    result = subprocess.run(
        ["python", "-m", "yt_dlp", "--flat-playlist",
         "--match-filter", "duration > 600 & duration < 7200",
         "--print", "%(id)s",
         channel_url],
        capture_output=True, text=True, timeout=600
    )
    ids = [i.strip() for i in result.stdout.strip().split("\n") if i.strip()]
    print(f"Found {len(ids)} qualifying videos")
    return ids

def clean_vtt(raw):
    raw = re.sub(r'WEBVTT\n.*?\n\n', '', raw, flags=re.DOTALL)
    lines = raw.split('\n')
    seen = set()
    cleaned = []
    for line in lines:
        if re.match(r'^\d{2}:\d{2}', line): continue
        if re.match(r'^\d+$', line.strip()): continue
        if line.strip() == '': continue
        if line.strip().startswith('NOTE'): continue
        line = re.sub(r'<[^>]+>', '', line).strip()
        if not line: continue
        if line not in seen:
            seen.add(line)
            cleaned.append(line)
    return ' '.join(cleaned)

def get_transcript(video_id):
    os.makedirs("C:/Temp", exist_ok=True)
    for f in os.listdir("C:/Temp"):
        if video_id in f:
            os.remove(f"C:/Temp/{f}")
    subprocess.run(
        ["python", "-m", "yt_dlp", "--skip-download", "--write-auto-sub",
         "--sub-format", "vtt", "--output", f"C:/Temp/{video_id}",
         f"https://www.youtube.com/watch?v={video_id}"],
        capture_output=True, text=True, timeout=60
    )
    vtt_files = [f for f in os.listdir("C:/Temp") if video_id in f and f.endswith(".vtt")]
    if not vtt_files:
        return None
    with open(f"C:/Temp/{vtt_files[0]}", encoding='utf-8') as f:
        raw = f.read()
    return clean_vtt(raw)

def chunk_text(text, size=500, overlap=50):
    words = text.split()
    chunks = []
    for i in range(0, len(words), size - overlap):
        chunks.append(" ".join(words[i:i + size]))
    return chunks

def already_processed(video_id):
    result = supabase.table("transcripts").select("id").eq("video_id", video_id).limit(1).execute()
    return len(result.data) > 0

def process_video(video_id):
    if already_processed(video_id):
        print(f"Skipping {video_id} — already in DB")
        return
    try:
        meta = subprocess.run(
            ["python", "-m", "yt_dlp", "--get-title",
             f"https://www.youtube.com/watch?v={video_id}"],
            capture_output=True, text=True, timeout=30
        )
        title = meta.stdout.strip() or video_id
    except subprocess.TimeoutExpired:
        title = video_id
    transcript = get_transcript(video_id)
    if not transcript:
        print(f"No transcript for {video_id}")
        return
    chunks = chunk_text(transcript)
    embeddings = [openai_client.embeddings.create(model="text-embedding-3-small", input=chunk).data[0].embedding for chunk in chunks]
    rows = [
        {"video_id": video_id, "title": title, "chunk_index": i, "content": chunk, "embedding": embedding}
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings))
    ]
    supabase.table("transcripts").insert(rows).execute()
    print(f"Done: {title} — {len(chunks)} chunks")

if __name__ == "__main__":
    ids = get_video_ids(CHANNEL_URL)
    for vid in ids:
        try:
            process_video(vid)
        except Exception as e:
            print(f"Error on {vid}: {e}")
            continue
