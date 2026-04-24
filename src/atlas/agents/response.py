"""
Response agent — formats STAC results into markdown for the chat panel.
"""

from atlas.state import AtlasState


async def response_node(state: AtlasState) -> dict:
    results = state.get("stac_results") or []
    params = state.get("search_params") or {}
    print(f"[response] formatting {len(results)} result(s)")

    loc = params.get("location_name", "that area")
    dr = params.get("date_range", ["?", "?"])
    cc = params.get("cloud_cover_max", 20)
    n = len(results)

    if n == 0:
        text = (
            f"No Sentinel-2 scenes found over **{loc}** between {dr[0]} and {dr[1]} "
            f"with cloud cover < {cc}%.\n\n"
            "Try:\n"
            "- Expanding the date range\n"
            "- Increasing cloud cover threshold (e.g. *less than 40% cloud cover*)\n"
            "- Using a broader area"
        )
        return {"response": text}

    lines = [
        f"Found **{n} Sentinel-2 scene{'s' if n != 1 else ''}** over **{loc}** "
        f"({dr[0]} → {dr[1]}, ☁️ < {cc}%).\n",
        "| Scene ID | Date | ☁️ | Thumbnail |",
        "|---|---|---|---|",
    ]

    for r in results:
        sid = r["id"]
        date = (r.get("datetime") or "")[:10]
        cloud = f"{r.get('cloud_cover', '?')}%"
        thumb = r.get("assets", {}).get("thumbnail", {}).get("href", "")
        thumb_md = f"[preview]({thumb})" if thumb else "—"
        lines.append(f"| `{sid}` | {date} | {cloud} | {thumb_md} |")

    if n > 0:
        lines.append("\nFootprints shown on the map. Click a scene to see download links.")

    return {"response": "\n".join(lines)}
