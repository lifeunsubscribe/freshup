/**
 * Executes an array of promise-returning functions with controlled concurrency.
 *
 * This utility prevents unbounded parallel API calls by limiting how many promises
 * can execute simultaneously. Useful for batch operations like adding multiple
 * items to a grocery list without overwhelming the backend.
 *
 * @template T - The type of value the promises resolve to
 * @param promiseFns - Array of functions that return promises to execute
 * @param concurrencyLimit - Maximum number of promises to execute concurrently (default: 5)
 * @returns Promise that resolves to array of PromiseSettledResult in original order
 *
 * @example
 * ```typescript
 * const items = ['apple', 'banana', 'orange']
 * const promiseFns = items.map(item => () => createGroceryItem(item))
 * const results = await batchPromises(promiseFns, 3)
 *
 * results.forEach((result, index) => {
 *   if (result.status === 'fulfilled') {
 *     console.log(`${items[index]} added successfully`)
 *   } else {
 *     console.error(`${items[index]} failed:`, result.reason)
 *   }
 * })
 * ```
 */
export async function batchPromises<T>(
  promiseFns: (() => Promise<T>)[],
  concurrencyLimit: number = 5
): Promise<PromiseSettledResult<T>[]> {
  // Validate inputs
  if (!Array.isArray(promiseFns)) {
    throw new TypeError('promiseFns must be an array')
  }

  if (!Number.isInteger(concurrencyLimit) || concurrencyLimit < 1) {
    throw new RangeError('concurrencyLimit must be a positive integer')
  }

  // Handle empty array
  if (promiseFns.length === 0) {
    return []
  }

  // Store results in order
  const results: PromiseSettledResult<T>[] = []
  let currentIndex = 0

  // Execute batch of promises
  const executeBatch = async (): Promise<void> => {
    while (currentIndex < promiseFns.length) {
      // Capture the current index for this iteration
      const index = currentIndex++
      const promiseFn = promiseFns[index]

      try {
        const value = await promiseFn()
        results[index] = { status: 'fulfilled', value }
      } catch (error) {
        results[index] = { status: 'rejected', reason: error }
      }
    }
  }

  // Create worker promises up to concurrency limit
  const workers = Math.min(concurrencyLimit, promiseFns.length)
  const workerPromises: Promise<void>[] = []

  for (let i = 0; i < workers; i++) {
    workerPromises.push(executeBatch())
  }

  // Wait for all workers to complete
  await Promise.all(workerPromises)

  return results
}
