import { describe, it, expect } from 'vitest'

// Two test files with the same name in different folders is how a stale test
// goes unnoticed: the new file passes and the old one, which nobody opened,
// fails on the change (or keeps passing while asserting nothing). A page that
// needs more than one test file gets a topic in each name instead, e.g.
// Recipes.library.test.tsx and Recipes.themes.test.tsx. See README.md, "Three
// things to know when writing frontend tests".
const testFiles = Object.keys(import.meta.glob('/src/**/*.test.{ts,tsx}'))

describe('test file names', () => {
  it('finds the test files', () => {
    expect(testFiles.length).toBeGreaterThan(50)
  })

  it('are not shared by two files in different folders', () => {
    const pathsByName = new Map<string, string[]>()
    for (const path of testFiles) {
      const name = path.slice(path.lastIndexOf('/') + 1)
      pathsByName.set(name, [...(pathsByName.get(name) ?? []), path])
    }
    const shared = [...pathsByName.values()].filter((paths) => paths.length > 1)
    expect(shared).toEqual([])
  })
})
