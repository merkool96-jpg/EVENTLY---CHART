const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const base = process.env.EVENTLY_URL || "http://127.0.0.1:8003";
(async () => {
  const b = await chromium.launch({
    headless: true,
    executablePath: process.env.BROWSER_EXECUTABLE || undefined,
    args: ["--no-sandbox"],
  });
  try {
    const p = await b.newPage({ viewport: { width: 1440, height: 1100 } });
    const errors = [];
    p.on("pageerror", (e) => errors.push(e.message));
    const initial = await (await p.request.get(base + "/api/people")).json();
    assert.equal(initial.length, 0, "Use a dedicated empty database");
    const event = await (
      await p.request.post(base + "/api/events", {
        data: {
          name: "Bottini Milano",
          date: "2026-11-07",
          participant_value_cents: 2000,
        },
      })
    ).json();
    const csv = Buffer.from(
      "Nome completo,Email\nSofia,sofia@example.test\nSofia Di Gio,sofia@example.test\n",
    );
    const upload = await p.request.post(
      base + "/api/events/" + event.id + "/import",
      {
        multipart: {
          file: { name: "sofia.csv", mimeType: "text/csv", buffer: csv },
          status: "confirmed",
        },
      },
    );
    assert.equal(upload.status(), 200);
    await p.goto(base);
    await p.getByRole("button", { name: "Identità", exact: true }).click();
    await p.getByRole("button", { name: "Unisci", exact: true }).click();
    const merge = p.getByRole("dialog", {
      name: "Scegli il profilo risultante",
    });
    await merge
      .getByRole("button", { name: /Consigliato dal sistema/ })
      .waitFor();
    assert.equal(
      await merge
        .getByLabel("Nominativo visualizzato", { exact: true })
        .inputValue(),
      "Sofia Di Gio",
    );
    await merge
      .getByRole("button", { name: "Primo nominativo Sofia", exact: true })
      .click();
    assert.equal(
      await merge
        .getByLabel("Nominativo visualizzato", { exact: true })
        .inputValue(),
      "Sofia",
    );
    await merge
      .getByRole("button", { name: /Consigliato dal sistema/ })
      .click();
    await merge
      .getByRole("button", { name: "Conferma unione", exact: true })
      .click();
    await merge.waitFor({ state: "hidden" });
    await p.getByRole("button", { name: "Partecipanti", exact: true }).click();
    await p.locator("tbody").getByText("Sofia Di Gio", { exact: true }).click();
    await p
      .getByRole("button", { name: "Modifica anagrafica", exact: true })
      .click();
    const edit = p.getByRole("dialog", { name: "Modifica anagrafica" });
    await edit.getByLabel("Cognome principale", { exact: true }).fill("Di Giò");
    await edit
      .getByLabel("Nominativo visualizzato", { exact: true })
      .fill("Sofia Di Giò");
    await edit.getByRole("button", { name: "Salva anagrafica" }).click();
    await edit.waitFor({ state: "hidden" });
    await p
      .getByRole("dialog", { name: "Profilo partecipante" })
      .getByRole("heading", { name: "Sofia Di Giò", exact: true })
      .waitFor();
    await p.getByRole("button", { name: "Chiudi", exact: true }).click();
    await p.getByRole("textbox", { name: "Cerca partecipante" }).fill("Di Gio");
    await p.waitForFunction(() => document.querySelectorAll("tbody tr").length === 1);
    assert.equal(await p.locator("tbody tr").count(), 1);
    await p
      .getByRole("button", { name: "Esporta partecipanti", exact: true })
      .click();
    const exp = p.getByRole("dialog", { name: "Esporta partecipanti" });
    await exp.getByRole("button", { name: "Scarica file" }).waitFor();
    await exp.locator("h2").filter({ hasText: "1" }).waitFor();
    const downloaded = p.waitForEvent("download");
    await exp.getByRole("button", { name: "Scarica file" }).click();
    const file = await downloaded;
    assert.equal(file.suggestedFilename(), "EVENTLY-partecipanti.xlsx");
    await file.saveAs("/tmp/evently-browser-export.xlsx");
    await exp.waitFor({ state: "hidden" });
    await p
      .getByRole("button", { name: "Esporta partecipanti", exact: true })
      .click();
    const exp2 = p.getByRole("dialog", { name: "Esporta partecipanti" });
    await exp2.getByLabel("Formato file", { exact: true }).selectOption("csv");
    await exp2
      .getByLabel("Ambito dei dati", { exact: true })
      .selectOption("filtered");
    const csvDownload = p.waitForEvent("download");
    await exp2.getByRole("button", { name: "Scarica file" }).click();
    assert.equal(
      (await csvDownload).suggestedFilename(),
      "EVENTLY-partecipanti.csv",
    );
    await exp2.waitFor({ state: "hidden" });
    await p.setViewportSize({ width: 390, height: 844 });
    await p
      .getByRole("button", { name: "Esporta partecipanti", exact: true })
      .click();
    assert.equal(
      await p.evaluate(() => document.documentElement.scrollWidth > innerWidth),
      false,
    );
    assert.deepEqual(errors, []);
    console.log(
      "Browser: scelta nome, raccomandazione, unione, modifica anagrafica, ricerca alias, download XLSX e CSV, mobile OK",
    );
  } finally {
    await b.close();
  }
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
