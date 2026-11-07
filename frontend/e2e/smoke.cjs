const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const URL = process.env.EVENTLY_URL || "http://127.0.0.1:8001";
(async () => {
  const browser = await chromium.launch({
    headless: true,
    executablePath: process.env.BROWSER_EXECUTABLE || undefined,
    args: ["--no-sandbox"],
  });
  try {
    const page = await browser.newPage({
      viewport: { width: 1440, height: 1100 },
    });
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    page.on("dialog", (d) => d.accept());
    const health = await page.request.get(URL + "/api/health");
    assert.equal(health.status(), 200);
    const existing = await (await page.request.get(URL + "/api/events")).json();
    assert.equal(
      existing.length,
      0,
      "Smoke test requires a dedicated empty database",
    );
    await page.goto(URL);
    await page.getByRole("button", { name: "Eventi", exact: true }).click();
    await page.getByRole("button", { name: "Nuovo evento" }).click();
    await page
      .getByLabel("Nome evento", { exact: true })
      .fill("Bottini Milano");
    await page.getByLabel("Data", { exact: true }).fill("2026-11-06");
    await page.locator("[name=participant_value]").fill("20");
    await page
      .getByRole("button", { name: "Salva evento", exact: true })
      .click();
    await page.getByRole("dialog").waitFor({ state: "hidden" });
    await page
      .getByRole("button", { name: "Importa partecipanti", exact: true })
      .click();
    await page.getByLabel("File partecipanti").setInputFiles({
      name: "ospiti.csv",
      mimeType: "text/csv",
      buffer: Buffer.from(
        "Nome completo,Email,Importo\nAnna Rossi,a@example.test,100\nAna Rossi,a@example.test,300\n",
      ),
    });
    await page.getByRole("button", { name: "Genera anteprima" }).waitFor();
    await page.getByLabel("Evento di destinazione").selectOption("1");
    await page.getByRole("button", { name: "Genera anteprima" }).click();
    await page.getByRole("button", { name: "Conferma importazione" }).waitFor();
    assert.deepEqual(
      await (await page.request.get(URL + "/api/people")).json(),
      [],
    );
    await page.getByRole("button", { name: "Conferma importazione" }).click();
    await page.getByRole("dialog").waitFor({ state: "hidden" });
    await page
      .getByRole("button", { name: "Partecipanti", exact: true })
      .click();
    await page.getByText("Anna Rossi", { exact: true }).click();
    await page.locator(".status-pill.registered").waitFor();
    await page
      .getByLabel("Stato registrazione 1", { exact: true })
      .selectOption("confirmed");
    await page.locator(".status-pill.confirmed").waitFor();
    await page.getByRole("button", { name: "Chiudi", exact: true }).click();
    await page.getByRole("button", { name: "Eventi", exact: true }).click();
    await page.getByRole("button", { name: "Modifica", exact: true }).click();
    await page.locator("[name=participant_value]").fill("40");
    await page
      .getByRole("button", { name: "Salva evento", exact: true })
      .click();
    await page.getByRole("dialog").waitFor({ state: "hidden" });
    await page.getByRole("button", { name: "Top 50", exact: true }).click();
    await page.getByText("Anna Rossi", { exact: true }).first().waitFor();
    let ps = await (
      await page.request.get(URL + "/api/people?ranked=true")
    ).json();
    assert.equal(ps[0].value, 4000);
    assert.equal(ps[0].visits, 1);
    await page.getByRole("button", { name: "Identità", exact: true }).click();
    await page.getByRole("button", { name: "Unisci", exact: true }).click();
    await page
      .getByRole("button", { name: "Conferma unione", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Annulla unione", exact: true })
      .waitFor();
    ps = await (await page.request.get(URL + "/api/people")).json();
    assert.equal(ps.length, 1);
    assert.equal(ps[0].value, 4000);
    await page
      .getByRole("button", { name: "Annulla unione", exact: true })
      .click();
    await page
      .getByRole("status")
      .filter({ hasText: "Unione annullata" })
      .waitFor();
    ps = await (await page.request.get(URL + "/api/people")).json();
    assert.equal(ps.length, 2);
    await page.getByRole("button", { name: "Top 50", exact: true }).click();
    await page.screenshot({
      path: "/tmp/evently-v11-top50.png",
      fullPage: true,
    });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({
      path: "/tmp/evently-v11-mobile.png",
      fullPage: true,
    });
    assert.equal(
      await page.evaluate(
        () => document.documentElement.scrollWidth > window.innerWidth,
      ),
      false,
    );
    assert.deepEqual(errors, []);
    console.log(
      "Browser V1.1: wizard + conferma, registrazione esclusa, conferma presenza, 20→40€, Top 3/50, unione/annullamento e mobile OK",
    );
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
