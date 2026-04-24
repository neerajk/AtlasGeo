"""
Response agent — formats STAC results and analysis outputs into markdown for the chat panel.
"""

from atlas.state import AtlasState


async def response_node(state: AtlasState) -> dict:
    results = state.get("stac_results") or []
    params = state.get("search_params") or {}
    output_tifs = state.get("output_tifs") or []
    task_type = params.get("task_type", "stac_search")
    print(f"[response] formatting {len(results)} result(s), {len(output_tifs)} analysis output(s)")

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

    # Flood mapping result
    if task_type == "flood_mapping" and output_tifs:
        tif = output_tifs[0]
        lines = [
            f"**Flood mapping complete** — {loc} ({dr[0]} → {dr[1]})\n",
            f"- **Scene:** `{tif['scene_id']}`",
            "- **Method:** MNDWI (Modified Normalised Difference Water Index)",
            f"- **Flooded area:** ~{tif['flood_area_km2']} km²",
            f"- **Flood pixels:** {tif['flood_pixels']:,}",
            "\nThe flood extent layer has been added to the map. "
            "Use the Layer Panel to toggle visibility and adjust opacity.",
        ]
        return {"response": "\n".join(lines)}

    if task_type == "flood_mapping" and not output_tifs:
        return {
            "response": (
                f"Found **{n} scene(s)** over **{loc}** but could not run flood analysis — "
                "scenes may be missing B03/B11 bands. Try a different date range."
            )
        }

    # Default STAC search result
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

    lines.append("\nFootprints shown on the map. Click a scene to see download links.")
    return {"response": "\n".join(lines)}
