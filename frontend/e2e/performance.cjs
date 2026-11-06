const { chromium } = require("playwright");
const assert = require("node:assert/strict");
(async () => {
  const b = await chromium.launch({
    headless: true,
    executablePath: process.env.BROWSER_EXECUTABLE || undefined,
    args: ["--no-sandbox"],
  });
  try {
    const p = await b.newPage();
    const errors = [];
    p.on("pageerror", (e) => errors.push(e.message));
    p.on("dialog", (d) => d.accept());
    let release;
    const gate = new Promise((resolve) => (release = resolve));
    let first = true;
    let holdPeople = false;
    let releasePeople;
    const peopleGate = new Promise((resolve) => (releasePeople = resolve));
    const delayedPeople = [];
    let decided = false;
    let merged = false;
    const counts = {};
    const people = [1, 2].map((id) => ({
      id,
      name: id === 1 ? "Mario Rossi" : "Mario Rosssi",
      email: "",
      phone: "",
      visits: 1,
      registrations: 0,
      unknown: 0,
      value: 2000,
      last_seen: "2026-11-06",
      undefined_values: 0,
      actual_spend: 0,
      members: [],
      incomplete: false,
    }));
    await p.route("**/api/**", async (route) => {
      const path = new URL(route.request().url()).pathname;
      const delayPeople = path === "/api/people" && holdPeople;
      counts[path] = (counts[path] || 0) + 1;
      let data = [];
      if (path === "/api/matches/decision") {
        decided = true;
        merged = route.request().postDataJSON().action === "merge";
        data = { ok: true };
      } else if (path === "/api/people")
        data = merged ? [{ ...people[0], members: people }] : people;
      else if (path === "/api/dashboard")
        data = {
          people: merged ? 1 : 2,
          events: 0,
          attributed_value: merged ? 2000 : 4000,
          undefined_events: 0,
          actual_spend: 0,
          cost: 0,
          attendance: merged ? 1 : 2,
          registrations: 0,
          unknown: 0,
          returning: 0,
          timeline: [],
        };
      else if (path === "/api/matches") {
        if (first) {
          await gate;
        }
        data = decided
          ? []
          : [
              {
                a: people[0],
                b: people[1],
                evidence: "surname_typo",
                reason:
                  "Possibile errore di battitura nel cognome; nome esatto",
              },
            ];
      }
      if (delayPeople) {
        const send = peopleGate.then(() => route.fulfill({ json: data }));
        delayedPeople.push(send);
        await send;
        return;
      }
      await route.fulfill({ json: data });
    });
    await p.goto(process.env.EVENTLY_URL || "http://127.0.0.1:5173");
    await p
      .locator(".metric h2")
      .filter({ hasText: "2" })
      .first()
      .waitFor({ timeout: 3000 });
    assert.ok(counts["/api/matches"] >= 1); // Matching is still blocked at this point.
    first = false;
    release();
    await p.getByRole("button", { name: "Identità", exact: true }).click();
    await p.getByRole("button", { name: "Mantieni separati" }).waitFor();
    const peopleBefore = counts["/api/people"],
      statsBefore = counts["/api/dashboard"],
      eventsBefore = counts["/api/events"];
    await p.getByRole("button", { name: "Mantieni separati" }).click();
    await p
      .getByText("Nessuna ambiguità da verificare", { exact: true })
      .waitFor();
    assert.equal(counts["/api/people"], peopleBefore);
    assert.equal(counts["/api/dashboard"], statsBefore);
    assert.equal(counts["/api/events"], eventsBefore);
    decided = false;
    await p.reload();
    await p.getByRole("button", { name: "Identità", exact: true }).click();
    await p.getByRole("button", { name: "Unisci", exact: true }).waitFor();
    const beforeMerge = counts["/api/people"];
    await p.getByRole("button", { name: "Unisci", exact: true }).click();
    await p
      .getByText("Nessuna ambiguità da verificare", { exact: true })
      .waitFor();
    assert.equal(counts["/api/people"], beforeMerge + 1);
    await p.getByRole("button", { name: "Partecipanti", exact: true }).click();
    await p.locator("tbody tr").first().waitFor();
    assert.equal(await p.locator("tbody tr").count(), 1);
    decided = false;
    merged = false;
    holdPeople = true;
    await p.reload();
    await p.getByRole("button", { name: "Identità", exact: true }).click();
    await p.getByRole("button", { name: "Unisci", exact: true }).waitFor();
    holdPeople = false;
    await p.getByRole("button", { name: "Unisci", exact: true }).click();
    await p
      .getByText("Nessuna ambiguità da verificare", { exact: true })
      .waitFor();
    await p.getByRole("button", { name: "Partecipanti", exact: true }).click();
    await p.locator("tbody tr").first().waitFor();
    assert.equal(await p.locator("tbody tr").count(), 1);
    releasePeople();
    await Promise.all(delayedPeople);
    await p.evaluate(
      () =>
        new Promise((resolve) =>
          requestAnimationFrame(() => requestAnimationFrame(resolve)),
        ),
    );
    assert.equal(
      await p.locator("tbody tr").count(),
      1,
      "Old responses must not restore the unmerged people",
    );
    assert.deepEqual(errors, []);
    console.log(
      "Browser performance OK: KPI visibili con matching in attesa; separazione senza ricaricare aggregati; unione aggiorna partecipanti e valori.",
    );
  } finally {
    await b.close();
  }
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
