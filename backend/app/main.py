@app.post("/api/admin/harvest")
async def admin_harvest(Authorization: str | None = Header(default=None)):
    require_admin(Authorization)
    provider = AFProvider()

    async with SessionLocal() as session:
        res = provider.fetch()
        jobs = await res if asyncio.iscoroutine(res) else res  # <-- funkar för båda fallen
        saved = 0
        for job in jobs:
            await upsert_job(session, job)
            saved += 1
        await session.commit()
    return {"ok": True, "counts": {provider.name: saved}}
