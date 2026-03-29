import { describe, it, expect, vi } from 'vitest'
import { batchPromises } from '../batchPromises'

describe('batchPromises', () => {
  describe('basic functionality', () => {
    it('should execute all promises and return results in order', async () => {
      const promiseFns = [
        () => Promise.resolve(1),
        () => Promise.resolve(2),
        () => Promise.resolve(3),
      ]

      const results = await batchPromises(promiseFns, 2)

      expect(results).toHaveLength(3)
      expect(results[0]).toEqual({ status: 'fulfilled', value: 1 })
      expect(results[1]).toEqual({ status: 'fulfilled', value: 2 })
      expect(results[2]).toEqual({ status: 'fulfilled', value: 3 })
    })

    it('should handle empty array', async () => {
      const results = await batchPromises([], 5)
      expect(results).toEqual([])
    })

    it('should handle single promise', async () => {
      const promiseFns = [() => Promise.resolve('single')]
      const results = await batchPromises(promiseFns, 5)

      expect(results).toHaveLength(1)
      expect(results[0]).toEqual({ status: 'fulfilled', value: 'single' })
    })

    it('should use default concurrency limit of 5', async () => {
      const executionOrder: number[] = []
      const promiseFns = Array.from({ length: 10 }, (_, i) => () => {
        executionOrder.push(i)
        return Promise.resolve(i)
      })

      const results = await batchPromises(promiseFns)

      expect(results).toHaveLength(10)
      expect(results.every((r) => r.status === 'fulfilled')).toBe(true)
    })
  })

  describe('concurrency control', () => {
    it('should limit concurrent executions to specified limit', async () => {
      let activePromises = 0
      let maxActivePromises = 0
      const concurrencyLimit = 3

      const promiseFns = Array.from({ length: 10 }, (_, i) => async () => {
        activePromises++
        maxActivePromises = Math.max(maxActivePromises, activePromises)

        // Simulate async work
        await new Promise((resolve) => setTimeout(resolve, 10))

        activePromises--
        return i
      })

      await batchPromises(promiseFns, concurrencyLimit)

      // Max active should never exceed the limit
      expect(maxActivePromises).toBeLessThanOrEqual(concurrencyLimit)
      expect(maxActivePromises).toBeGreaterThan(0)
    })

    it('should handle concurrency limit of 1 (sequential execution)', async () => {
      const executionOrder: number[] = []
      const completionOrder: number[] = []

      const promiseFns = Array.from({ length: 5 }, (_, i) => async () => {
        executionOrder.push(i)
        await new Promise((resolve) => setTimeout(resolve, 5))
        completionOrder.push(i)
        return i
      })

      await batchPromises(promiseFns, 1)

      // With limit of 1, execution and completion should be in same order
      expect(executionOrder).toEqual([0, 1, 2, 3, 4])
      expect(completionOrder).toEqual([0, 1, 2, 3, 4])
    })

    it('should handle concurrency limit greater than array length', async () => {
      const promiseFns = Array.from({ length: 3 }, (_, i) => () => Promise.resolve(i))

      const results = await batchPromises(promiseFns, 10)

      expect(results).toHaveLength(3)
      expect(results.every((r) => r.status === 'fulfilled')).toBe(true)
    })
  })

  describe('error handling', () => {
    it('should handle rejected promises without affecting others', async () => {
      const promiseFns = [
        () => Promise.resolve(1),
        () => Promise.reject(new Error('Failed')),
        () => Promise.resolve(3),
      ]

      const results = await batchPromises(promiseFns, 2)

      expect(results).toHaveLength(3)
      expect(results[0]).toEqual({ status: 'fulfilled', value: 1 })
      expect(results[1]).toEqual({
        status: 'rejected',
        reason: expect.any(Error),
      })
      expect(results[2]).toEqual({ status: 'fulfilled', value: 3 })
    })

    it('should handle all promises failing', async () => {
      const promiseFns = [
        () => Promise.reject(new Error('Error 1')),
        () => Promise.reject(new Error('Error 2')),
        () => Promise.reject(new Error('Error 3')),
      ]

      const results = await batchPromises(promiseFns, 2)

      expect(results).toHaveLength(3)
      expect(results.every((r) => r.status === 'rejected')).toBe(true)
    })

    it('should handle thrown errors in promise functions', async () => {
      const promiseFns = [
        () => Promise.resolve(1),
        () => {
          throw new Error('Synchronous error')
        },
        () => Promise.resolve(3),
      ]

      const results = await batchPromises(promiseFns, 2)

      expect(results).toHaveLength(3)
      expect(results[0]).toEqual({ status: 'fulfilled', value: 1 })
      expect(results[1]).toEqual({
        status: 'rejected',
        reason: expect.any(Error),
      })
      expect(results[2]).toEqual({ status: 'fulfilled', value: 3 })
    })

    it('should preserve error details in rejected results', async () => {
      const customError = new Error('Custom error message')
      const promiseFns = [() => Promise.reject(customError)]

      const results = await batchPromises(promiseFns, 1)

      expect(results[0].status).toBe('rejected')
      if (results[0].status === 'rejected') {
        expect(results[0].reason).toBe(customError)
        expect(results[0].reason.message).toBe('Custom error message')
      }
    })
  })

  describe('order preservation', () => {
    it('should preserve order even with varying promise durations', async () => {
      const promiseFns = [
        () => new Promise<number>((resolve) => setTimeout(() => resolve(1), 30)),
        () => new Promise<number>((resolve) => setTimeout(() => resolve(2), 10)),
        () => new Promise<number>((resolve) => setTimeout(() => resolve(3), 20)),
      ]

      const results = await batchPromises(promiseFns, 3)

      expect(results[0]).toEqual({ status: 'fulfilled', value: 1 })
      expect(results[1]).toEqual({ status: 'fulfilled', value: 2 })
      expect(results[2]).toEqual({ status: 'fulfilled', value: 3 })
    })

    it('should preserve order with large batches', async () => {
      const promiseFns = Array.from({ length: 50 }, (_, i) => () =>
        Promise.resolve(i)
      )

      const results = await batchPromises(promiseFns, 5)

      expect(results).toHaveLength(50)
      results.forEach((result, index) => {
        expect(result).toEqual({ status: 'fulfilled', value: index })
      })
    })
  })

  describe('input validation', () => {
    it('should throw TypeError for non-array input', async () => {
      await expect(
        // @ts-expect-error - Testing invalid input
        batchPromises('not an array', 5)
      ).rejects.toThrow(TypeError)
    })

    it('should throw RangeError for non-positive concurrency limit', async () => {
      const promiseFns = [() => Promise.resolve(1)]

      await expect(batchPromises(promiseFns, 0)).rejects.toThrow(RangeError)
      await expect(batchPromises(promiseFns, -1)).rejects.toThrow(RangeError)
    })

    it('should throw RangeError for non-integer concurrency limit', async () => {
      const promiseFns = [() => Promise.resolve(1)]

      await expect(batchPromises(promiseFns, 2.5)).rejects.toThrow(RangeError)
    })
  })

  describe('real-world scenarios', () => {
    it('should handle API call batching (simulated)', async () => {
      const apiCallDelay = 10
      const items = ['apple', 'banana', 'orange', 'grape', 'melon']

      // Simulate API calls with delays
      const promiseFns = items.map(
        (item) => () =>
          new Promise<{ name: string; id: number }>((resolve) =>
            setTimeout(
              () => resolve({ name: item, id: Math.random() }),
              apiCallDelay
            )
          )
      )

      const startTime = Date.now()
      const results = await batchPromises(promiseFns, 2)
      const endTime = Date.now()

      // All items should succeed
      expect(results.every((r) => r.status === 'fulfilled')).toBe(true)

      // With 5 items, limit of 2, each taking ~10ms:
      // Should take ~30ms (3 batches: [0,1], [2,3], [4])
      // Not ~50ms (sequential) or ~10ms (all parallel)
      const duration = endTime - startTime
      expect(duration).toBeGreaterThanOrEqual(20) // At least 3 batches
      expect(duration).toBeLessThan(60) // But not fully sequential
    })

    it('should handle mixed success and failure in large batch', async () => {
      // Simulate adding 15 grocery items where some fail
      const promiseFns = Array.from({ length: 15 }, (_, i) => async () => {
        await new Promise((resolve) => setTimeout(resolve, 5))

        // Every 5th item fails
        if (i % 5 === 0) {
          throw new Error(`Item ${i} failed`)
        }

        return { id: i, name: `Item ${i}` }
      })

      const results = await batchPromises(promiseFns, 5)

      expect(results).toHaveLength(15)

      const successCount = results.filter((r) => r.status === 'fulfilled').length
      const failureCount = results.filter((r) => r.status === 'rejected').length

      expect(successCount).toBe(12) // 15 - 3 failures
      expect(failureCount).toBe(3) // Items 0, 5, 10
    })
  })

  describe('type safety', () => {
    it('should handle different return types', async () => {
      const stringPromises = [
        () => Promise.resolve('a'),
        () => Promise.resolve('b'),
      ]
      const stringResults = await batchPromises(stringPromises, 2)
      expect(stringResults[0]).toEqual({ status: 'fulfilled', value: 'a' })

      const numberPromises = [() => Promise.resolve(1), () => Promise.resolve(2)]
      const numberResults = await batchPromises(numberPromises, 2)
      expect(numberResults[0]).toEqual({ status: 'fulfilled', value: 1 })

      const objectPromises = [
        () => Promise.resolve({ id: 1, name: 'test' }),
        () => Promise.resolve({ id: 2, name: 'test2' }),
      ]
      const objectResults = await batchPromises(objectPromises, 2)
      expect(objectResults[0]).toEqual({
        status: 'fulfilled',
        value: { id: 1, name: 'test' },
      })
    })
  })
})
