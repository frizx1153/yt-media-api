from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import asyncio
import re
from typing import Optional

app = FastAPI(title="YouTube Media API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

ydl_opts = {
    "quiet": True,
    "no_warnings": True,
    "extract_flat": False,
}


def search_youtube(query: str, max_results: int = 10) -> list:
    opts = {**ydl_opts, "extract_flat": "in_playlist"}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
        if not info or "entries" not in info:
            return []
        return [
            {
                "id": entry.get("id"),
                "title": entry.get("title"),
                "url": f"https://www.youtube.com/watch?v={entry.get('id')}",
                "duration": entry.get("duration"),
                "thumbnail": entry.get("thumbnail"),
                "channel": entry.get("channel"),
                "channel_url": entry.get("channel_url"),
                "view_count": entry.get("view_count"),
            }
            for entry in info["entries"]
            if entry
        ]


def get_video_info(url: str) -> dict:
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return {
            "id": info.get("id"),
            "title": info.get("title"),
            "description": info.get("description"),
            "duration": info.get("duration"),
            "thumbnail": info.get("thumbnail"),
            "channel": info.get("channel"),
            "channel_url": info.get("channel_url"),
            "view_count": info.get("view_count"),
            "like_count": info.get("like_count"),
            "tags": info.get("tags"),
            "categories": info.get("categories"),
            "formats": [
                {
                    "format_id": f.get("format_id"),
                    "ext": f.get("ext"),
                    "resolution": f.get("resolution"),
                    "filesize": f.get("filesize"),
                    "abr": f.get("abr"),
                    "vbr": f.get("vbr"),
                    "url": f.get("url"),
                    "format_note": f.get("format_note"),
                    "vcodec": f.get("vcodec"),
                    "acodec": f.get("acodec"),
                }
                for f in (info.get("formats") or [])
                if f.get("ext")
            ],
        }


MUSIC_QUERY_PAGES = [
    [
        "hindi official music video",
        "bhojpuri official music video",
        "tamil official music video",
        "telugu official music video",
        "malayalam official music video",
    ],
    [
        "kannada official music video",
        "bengali official music video",
        "marathi official music video",
        "gujarati official music video",
        "punjabi official music video",
    ],
    [
        "odia official music video",
        "assamese official music video",
        "urdu official music video",
        "indian pop song official video",
        "english official music video",
    ],
]

DANCE_QUERY_PAGES = [
    [
        "dance reel",
        "dance shorts",
        "dance choreography",
        "dance video trending",
    ],
    [
        "hip hop dance",
        "bollywood dance cover",
        "indian dance reel",
        "dance performance",
    ],
    [
        "freestyle dance",
        "dance tutorial",
        "party dance",
        "street dance",
    ],
]


def fetch_page_results(queries: list, results_per_query: int, seen_ids: set) -> list:
    opts = {**ydl_opts, "extract_flat": "in_playlist"}
    results = []
    for query in queries:
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f"ytsearch{results_per_query}:{query}", download=False)
                if info and "entries" in info:
                    for entry in info["entries"]:
                        if entry and entry.get("id") and entry["id"] not in seen_ids:
                            seen_ids.add(entry["id"])
                            results.append({
                                "id": entry.get("id"),
                                "title": entry.get("title"),
                                "url": f"https://www.youtube.com/watch?v={entry.get('id')}",
                                "duration": entry.get("duration"),
                                "thumbnail": entry.get("thumbnail"),
                                "channel": entry.get("channel"),
                                "channel_url": entry.get("channel_url"),
                                "view_count": entry.get("view_count"),
                            })
        except Exception:
            continue
    return results


def extract_audio_formats(info: dict) -> list:
    return [
        {
            "format_id": f.get("format_id"),
            "ext": f.get("ext"),
            "abr": f.get("abr"),
            "filesize": f.get("filesize"),
            "format_note": f.get("format_note"),
        }
        for f in (info.get("formats") or [])
        if f.get("acodec") and f.get("acodec") != "none"
    ]


@app.get("/music")
async def music(
    page: int = Query(1, ge=1, description="Page number"),
    per_query: int = Query(5, ge=1, le=10, description="Results per search query"),
):
    loop = asyncio.get_event_loop()
    page_idx = (page - 1) % len(MUSIC_QUERY_PAGES)
    queries = MUSIC_QUERY_PAGES[page_idx]
    seen = set()
    results = await loop.run_in_executor(None, fetch_page_results, queries, per_query, seen)
    return {"count": len(results), "results": results, "page": page}


@app.get("/dance")
async def dance(
    page: int = Query(1, ge=1, description="Page number"),
    per_query: int = Query(5, ge=1, le=10, description="Results per search query"),
):
    loop = asyncio.get_event_loop()
    page_idx = (page - 1) % len(DANCE_QUERY_PAGES)
    queries = DANCE_QUERY_PAGES[page_idx]
    seen = set()
    results = await loop.run_in_executor(None, fetch_page_results, queries, per_query, seen)
    return {"count": len(results), "results": results, "page": page}


@app.get("/search")
async def search(
    q: str = Query(..., description="Search query"),
    category: Optional[str] = Query(None, description="Filter: music or dance"),
    max_results: int = Query(10, ge=1, le=50, description="Max results"),
):
    query = q
    if category:
        query = f"{q} {category} song"

    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, search_youtube, query, max_results)
    return {"query": q, "category": category, "count": len(results), "results": results}


@app.get("/info")
async def info(url: str = Query(..., description="YouTube video URL")):
    loop = asyncio.get_event_loop()
    try:
        video_info = await loop.run_in_executor(None, get_video_info, url)
        return video_info
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/audio")
async def audio(url: str = Query(..., description="YouTube video URL")):
    loop = asyncio.get_event_loop()
    try:
        info = await loop.run_in_executor(
            None, lambda: get_video_info(url)
        )
        audio_formats = extract_audio_formats(info)
        return {
            "title": info["title"],
            "duration": info["duration"],
            "audio_formats": audio_formats,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


def parse_height(resolution: str) -> int:
    if not resolution:
        return 0
    nums = re.findall(r'\d+', str(resolution))
    if len(nums) >= 2:
        h = max(int(nums[0]), int(nums[1]))
    elif nums:
        h = int(nums[0])
    else:
        h = 0
    return h if h <= 4320 else 0


@app.get("/stream")
async def stream(url: str = Query(..., description="YouTube video URL")):
    loop = asyncio.get_event_loop()
    try:
        info = await loop.run_in_executor(None, lambda: get_video_info(url))
        formats = info.get("formats", [])

        usable = [f for f in formats if f.get("vcodec") and f["vcodec"] != "none" and f.get("acodec") and f["acodec"] != "none" and f.get("url")]

        if usable:
            usable.sort(key=lambda f: parse_height(f.get("resolution", "")), reverse=True)
            best = usable[0]
        else:
            fallback = [f for f in formats if f.get("url")]
            if not fallback:
                raise HTTPException(status_code=404, detail="No playable format found")
            fallback.sort(key=lambda f: parse_height(f.get("resolution", "")), reverse=True)
            best = fallback[0]

        return RedirectResponse(url=best["url"])
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/")
async def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/health")
async def health():
    return {"status": "ok"}
