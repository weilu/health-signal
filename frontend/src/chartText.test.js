import { describe, expect, it } from 'vitest'
import i18next from 'i18next'
import { chartSubtitle, chartTitle } from './labels.js'

async function translator(resources) {
  const i18n = i18next.createInstance()
  await i18n.init({ lng: 'en', resources: { en: { translation: resources } }, interpolation: { escapeValue: false } })
  return i18n.t
}

const library = { chart: { title: { full: '{{name}} · {{pathogen}} ({{location}})', pathogen: '{{name}} · {{pathogen}}',
                                      location: '{{name}} ({{location}})' } },
                  targets: { 'SARS-CoV-2': 'COVID-19' }, indicators: { hospitaladmissions: 'Hospital admissions' } }
const target = { id: 'SARS-CoV-2', label_key: 'targets.SARS-CoV-2' }
const attica = { value: 'Attica', label: 'Attica' }
const panel = (pathogen) => ({ id: 'hospital_admissions', type: 'timeseries', label_key: 'panels.hospital_admissions',
                               name: { indicator: 'hospitaladmissions', dimensions: {}, pathogen } })

describe('chartTitle', () => {
  it('names the pathogen and location, so a chart keeps its context below the tabs', async () =>
    expect(chartTitle(await translator(library), panel(true), target, attica)).toBe('Hospital admissions · COVID-19 (Attica)'))
  it("leaves out a pathogen the panel doesn't belong to or already names", async () =>
    expect(chartTitle(await translator(library), panel(false), target, attica)).toBe('Hospital admissions (Attica)'))
  it('leaves out the location without a location filter', async () =>
    expect(chartTitle(await translator(library), panel(true), target, null)).toBe('Hospital admissions · COVID-19'))
  it("names a card about the whole tab by the tab's pathogen too, so it keeps its context once cropped", async () => {
    const card = { id: 'phase', type: 'phase', label_key: 'panels.phase' }
    expect(chartTitle(await translator({ ...library, panelTypes: { phase: 'Key signals' } }), card, target, attica))
      .toBe('Key signals · COVID-19 (Attica)')
  })
})

describe('chartSubtitle', () => {
  const subtitles = {
    hospital_admissions: 'Weekly new {{pathogen}} admissions, nationally.',
    hospital_admissions_Attica: 'Weekly new {{pathogen}} admissions from the {{location}} hospitals.',
    'SARS-CoV-2': { hospital_admissions: 'COVID, nationally.' },
  }
  it("fills a deployment's subtitle with the pathogen and location", async () => {
    const t = await translator({ ...library, subtitles: { hospital_admissions: subtitles.hospital_admissions } })
    expect(chartSubtitle(t, panel(true), { id: 'Influenza', label_key: 'targets.Influenza' }, null))
      .toBe('Weekly new Influenza admissions, nationally.')
  })
  it('prefers a location variant, then a target-specific one', async () => {
    const t = await translator({ ...library, subtitles })
    const flu = { id: 'Influenza', label_key: 'targets.Influenza' }
    expect(chartSubtitle(t, panel(true), flu, attica)).toBe('Weekly new Influenza admissions from the Attica hospitals.')
    expect(chartSubtitle(t, panel(true), target, { value: 'Greece', label: 'Greece' })).toBe('COVID, nationally.')
  })
  it('is empty where the deployment gives none', async () =>
    expect(chartSubtitle(await translator(library), panel(true), target, attica)).toBe(''))
})
