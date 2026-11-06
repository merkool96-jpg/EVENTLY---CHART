const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const url = process.env.EVENTLY_URL || "http://127.0.0.1:5173";
(async () => {
  const browser = await chromium.launch({
    headless: true,
    executablePath: process.env.BROWSER_EXECUTABLE || undefined,
    args: ["--no-sandbox"],
  });
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    const people = Array.from({ length: 66 }, (_, i) => ({
      id: i + 1,
      name: `Persona ${String(i + 1).padStart(2, "0")}`,
      email: `p${i + 1}@example.test`,
      phone: "",
      visits: i === 65 ? 0 : 65 - i,
      registrations: (i + 1) % 10,
      unknown: 0,
      value: i === 65 ? 9999999 : (i + 1) * 100,
      last_seen:
        i % 5 === 0 ? null : `2026-10-${String((i % 28) + 1).padStart(2, "0")}`,
      members: [],
      incomplete: false,
      undefined_values: 0,
      actual_spend: 0,
    }));
    const original = JSON.stringify(people);
    await page.route("**/api/**", async (route) => {
      assert.equal(
        route.request().method(),
        "GET",
        "Sorting must never modify data",
      );
      const path = new URL(route.request().url()).pathname;
      const data =
        path === "/api/people"
          ? people
          : path === "/api/dashboard"
            ? {
                people: 66,
                events: 0,
                attributed_value: 0,
                undefined_events: 0,
                actual_spend: 0,
                cost: 0,
                attendance: 0,
                registrations: 0,
                unknown: 0,
                returning: 0,
                timeline: [],
              }
            : [];
      await route.fulfill({ json: data });
    });
    await page.goto(url);
    await page
      .getByRole("button", { name: "Partecipanti", exact: true })
      .click();
    const names = () =>
      page.locator("tbody .person-cell strong").allTextContents();
    await page.locator("tbody tr").first().waitFor();
    assert.equal((await names())[0], "Persona 01");
    const sort = (label) =>
      page
        .getByRole("button", { name: "Ordina per " + label, exact: true })
        .click();
    await sort("Valore attribuito");
    assert.equal((await names())[0], "Persona 66");
    assert.equal(
      await page
        .getByRole("columnheader")
        .filter({
          has: page.getByRole("button", {
            name: "Ordina per Valore attribuito",
            exact: true,
          }),
        })
        .getAttribute("aria-sort"),
      "descending",
    );
    await sort("Valore attribuito");
    assert.equal((await names())[0], "Persona 01");
    await sort("Partecipante");
    assert.equal((await names())[0], "Persona 01");
    await sort("Partecipante");
    assert.equal((await names())[0], "Persona 66");
    await sort("Presenze");
    assert.equal((await names())[0], "Persona 01");
    await sort("Presenze");
    assert.equal((await names())[0], "Persona 66");
    await sort("Registrazioni");
    assert.equal((await names())[0], "Persona 09");
    await sort("Ultimo incontro");
    let list = await names();
    assert.equal(list.at(-1), "Persona 66");
    await sort("Ultimo incontro");
    list = await names();
    assert.equal(list.at(-1), "Persona 66");
    await page
      .getByRole("button", { name: "Ripristina classifica per presenze" })
      .click();
    await page.getByRole("button", { name: "Top 50", exact: true }).click();
    assert.equal((await names()).length, 50);
    assert.equal((await names()).includes("Persona 65"), false);
    await sort("Valore attribuito");
    list = await names();
    assert.equal(list.length, 50);
    assert.equal(list[0], "Persona 65");
    assert.equal(list.includes("Persona 66"), false);
    assert.deepEqual(await page.locator(".podium h3").allTextContents(), [
      "Persona 65",
      "Persona 64",
      "Persona 63",
    ]);
    await page
      .getByRole("textbox", { name: "Cerca partecipante" })
      .fill("Persona 65");
    assert.deepEqual(await names(), ["Persona 65"]);
    await page.getByRole("textbox", { name: "Cerca partecipante" }).fill("");
    assert.equal((await names())[0], "Persona 65");
    await page
      .getByRole("button", { name: "Ripristina classifica per presenze" })
      .click();
    assert.equal((await names())[0], "Persona 01");
    await page
      .getByRole("button", {
        name: "Ordina per Valore attribuito",
        exact: true,
      })
      .focus();
    await page.keyboard.press("Enter");
    assert.equal((await names())[0], "Persona 65");
    await page.setViewportSize({ width: 390, height: 844 });
    assert.equal(
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      ),
      false,
    );
    assert.equal(JSON.stringify(people), original);
    assert.deepEqual(errors, []);
    console.log(
      "Ordinamento browser OK: 5 criteri, inversione, date mancanti, nuove Top 50/3, ricerca, reset, tastiera e mobile; nessuna modifica ai dati.",
    );
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
