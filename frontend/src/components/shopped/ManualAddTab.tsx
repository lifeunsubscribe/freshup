import { useState, useEffect, useRef, FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useCreateInventoryItem } from '../../api'
import { Category, StorageLocation } from '../../api/types'

/**
 * ManualAddTab component - Manual inventory item entry form
 *
 * Features:
 * - Form fields: name, quantity, unit, category, storage, store, expiration
 * - Smart defaults: quantity=1, unit="unit", category=OTHER, storage=PANTRY
 * - Two action modes:
 *   - "Add another": Creates item, clears form, stays on page
 *   - "Done": Creates item (if form has data), navigates to /pantry
 * - Form validation with user-friendly error messages
 * - Success feedback for each item added
 */
export default function ManualAddTab() {
  const navigate = useNavigate()
  const createInventoryMutation = useCreateInventoryItem()

  // Form state
  const [name, setName] = useState('')
  const [quantity, setQuantity] = useState('1')
  const [unit, setUnit] = useState('unit')
  const [category, setCategory] = useState<Category>(Category.OTHER)
  const [storageLocation, setStorageLocation] = useState<StorageLocation>(StorageLocation.PANTRY)
  const [store, setStore] = useState('')
  const [expirationDate, setExpirationDate] = useState('')

  // UI state
  const [showSuccess, setShowSuccess] = useState(false)
  const [lastAddedItemName, setLastAddedItemName] = useState('')
  const [validationError, setValidationError] = useState('')

  // Ref to store timeout ID for cleanup
  const successToastTimeoutRef = useRef<NodeJS.Timeout | null>(null)

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (successToastTimeoutRef.current) {
        clearTimeout(successToastTimeoutRef.current)
      }
    }
  }, [])

  /**
   * Checks if form has any user input (to decide whether "Done" should submit)
   */
  const isFormDirty = (): boolean => {
    return name.trim().length > 0
  }

  /**
   * Validates form and returns error message if invalid, null if valid
   */
  const validateForm = (): string | null => {
    if (!name.trim()) {
      return 'Item name is required'
    }
    const qtyNum = parseFloat(quantity)
    if (!Number.isFinite(qtyNum) || qtyNum <= 0) {
      return 'Quantity must be greater than 0'
    }
    if (qtyNum > 999999) {
      return 'Quantity must be less than 1,000,000'
    }
    if (!unit.trim()) {
      return 'Unit is required'
    }
    return null
  }

  /**
   * Clears all form fields to initial state
   */
  const clearForm = () => {
    setName('')
    setQuantity('1')
    setUnit('unit')
    setCategory(Category.OTHER)
    setStorageLocation(StorageLocation.PANTRY)
    setStore('')
    setExpirationDate('')
    setValidationError('')
  }

  /**
   * Submits the form to create an inventory item
   */
  const handleSubmit = async (e?: FormEvent) => {
    e?.preventDefault()

    // Clear any previous validation errors
    setValidationError('')

    // Validate form
    const error = validateForm()
    if (error) {
      setValidationError(error)
      return false
    }

    try {
      // Create inventory item via API
      await createInventoryMutation.mutateAsync({
        name: name.trim(),
        quantity: parseFloat(quantity),
        unit: unit.trim(),
        category: category,
        storage_location: storageLocation,
        preferred_store: store.trim() || undefined,
        expiration_date: expirationDate || undefined,
      })

      // Show success message
      setLastAddedItemName(name.trim())
      setShowSuccess(true)

      // Clear any existing timeout before setting a new one
      if (successToastTimeoutRef.current) {
        clearTimeout(successToastTimeoutRef.current)
      }

      // Set new timeout and store the ID for cleanup
      successToastTimeoutRef.current = setTimeout(() => {
        setShowSuccess(false)
        successToastTimeoutRef.current = null
      }, 2000)

      return true
    } catch (error) {
      // Provide user feedback for submission failure
      console.error('Failed to create inventory item:', error)
      setValidationError('Failed to add item. Please try again.')
      return false
    }
  }

  /**
   * "Add another" handler: submit form and clear for next entry
   */
  const handleAddAnother = async (e: FormEvent) => {
    e.preventDefault()
    const success = await handleSubmit()
    if (success) {
      clearForm()
    }
  }

  /**
   * "Done" handler: submit form if dirty, then navigate to pantry
   */
  const handleDone = async (e: FormEvent) => {
    e.preventDefault()

    // If form has data, submit it first
    if (isFormDirty()) {
      const success = await handleSubmit()
      if (!success) {
        // Don't navigate if submission failed
        return
      }
    }

    // Navigate to pantry
    navigate('/pantry')
  }

  return (
    <div className="pb-24">
      {/* Success toast */}
      {showSuccess && (
        <div
          className="fixed top-4 left-1/2 transform -translate-x-1/2 z-50 bg-olive text-white px-6 py-3 rounded-button shadow-lg"
          role="alert"
        >
          <p className="text-sm font-medium">
            {lastAddedItemName} added to pantry!
          </p>
        </div>
      )}

      <form onSubmit={handleAddAnother}>
        <div className="bg-white rounded-card border border-warm-border p-6">
          <h2 className="text-lg font-medium text-text-primary mb-4">
            Add item to pantry
          </h2>

          {/* Item name */}
          <div className="mb-4">
            <label
              htmlFor="item-name"
              className="block text-sm font-medium text-text-primary mb-1"
            >
              Item name *
            </label>
            <input
              type="text"
              id="item-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-3 py-2 border border-warm-border rounded-md focus:outline-none focus:ring-2 focus:ring-olive focus:border-transparent"
              placeholder="e.g., Olive oil"
              required
            />
          </div>

          {/* Quantity and Unit - side by side */}
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <label
                htmlFor="quantity"
                className="block text-sm font-medium text-text-primary mb-1"
              >
                Quantity *
              </label>
              <input
                type="number"
                id="quantity"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                className="w-full px-3 py-2 border border-warm-border rounded-md focus:outline-none focus:ring-2 focus:ring-olive focus:border-transparent"
                min="0.01"
                step="0.01"
                required
              />
            </div>
            <div>
              <label
                htmlFor="unit"
                className="block text-sm font-medium text-text-primary mb-1"
              >
                Unit *
              </label>
              <input
                type="text"
                id="unit"
                value={unit}
                onChange={(e) => setUnit(e.target.value)}
                className="w-full px-3 py-2 border border-warm-border rounded-md focus:outline-none focus:ring-2 focus:ring-olive focus:border-transparent"
                placeholder="e.g., bottle, lb, oz"
                required
              />
            </div>
          </div>

          {/* Category */}
          <div className="mb-4">
            <label
              htmlFor="category"
              className="block text-sm font-medium text-text-primary mb-1"
            >
              Category *
            </label>
            <select
              id="category"
              value={category}
              onChange={(e) => setCategory(e.target.value as Category)}
              className="w-full px-3 py-2 border border-warm-border rounded-md focus:outline-none focus:ring-2 focus:ring-olive focus:border-transparent"
              required
            >
              <option value={Category.PRODUCE}>Produce</option>
              <option value={Category.DAIRY}>Dairy</option>
              <option value={Category.PROTEIN}>Protein</option>
              <option value={Category.GRAINS}>Grains</option>
              <option value={Category.CONDIMENTS}>Condiments</option>
              <option value={Category.SNACKS}>Snacks</option>
              <option value={Category.BEVERAGES}>Beverages</option>
              <option value={Category.FROZEN}>Frozen</option>
              <option value={Category.CANNED}>Canned</option>
              <option value={Category.BAKING}>Baking</option>
              <option value={Category.SPICES}>Spices</option>
              <option value={Category.OTHER}>Other</option>
            </select>
          </div>

          {/* Storage location */}
          <div className="mb-4">
            <label
              htmlFor="storage-location"
              className="block text-sm font-medium text-text-primary mb-1"
            >
              Storage location *
            </label>
            <select
              id="storage-location"
              value={storageLocation}
              onChange={(e) => setStorageLocation(e.target.value as StorageLocation)}
              className="w-full px-3 py-2 border border-warm-border rounded-md focus:outline-none focus:ring-2 focus:ring-olive focus:border-transparent"
              required
            >
              <option value={StorageLocation.PANTRY}>Pantry</option>
              <option value={StorageLocation.FRIDGE}>Fridge</option>
              <option value={StorageLocation.FREEZER}>Freezer</option>
              <option value={StorageLocation.COUNTER}>Counter</option>
            </select>
          </div>

          {/* Store (optional) */}
          <div className="mb-4">
            <label
              htmlFor="store"
              className="block text-sm font-medium text-text-primary mb-1"
            >
              Store <span className="text-text-tertiary">(optional)</span>
            </label>
            <input
              type="text"
              id="store"
              value={store}
              onChange={(e) => setStore(e.target.value)}
              className="w-full px-3 py-2 border border-warm-border rounded-md focus:outline-none focus:ring-2 focus:ring-olive focus:border-transparent"
              placeholder="e.g., Whole Foods"
            />
          </div>

          {/* Expiration date (optional) */}
          <div className="mb-6">
            <label
              htmlFor="expiration-date"
              className="block text-sm font-medium text-text-primary mb-1"
            >
              Expiration date <span className="text-text-tertiary">(optional)</span>
            </label>
            <input
              type="date"
              id="expiration-date"
              value={expirationDate}
              onChange={(e) => setExpirationDate(e.target.value)}
              className="w-full px-3 py-2 border border-warm-border rounded-md focus:outline-none focus:ring-2 focus:ring-olive focus:border-transparent"
            />
          </div>

          {/* Validation error */}
          {validationError && (
            <div
              className="mb-4 px-3 py-2 bg-red-50 border border-red-200 rounded-md text-sm text-red-800"
              role="alert"
            >
              {validationError}
            </div>
          )}

          {/* API error */}
          {createInventoryMutation.isError && (
            <div
              className="mb-4 px-3 py-2 bg-red-50 border border-red-200 rounded-md text-sm text-red-800"
              role="alert"
            >
              Failed to add item. Please try again.
            </div>
          )}

          {/* Action buttons */}
          <div className="flex gap-3">
            <button
              type="submit"
              disabled={createInventoryMutation.isPending}
              className="flex-1 py-3 bg-white text-olive border-2 border-olive rounded-button font-medium hover:bg-cream transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {createInventoryMutation.isPending ? 'Adding...' : 'Add another'}
            </button>
            <button
              type="button"
              onClick={handleDone}
              disabled={createInventoryMutation.isPending}
              className="flex-1 py-3 bg-olive text-white rounded-button font-medium hover:bg-olive-dark transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Done
            </button>
          </div>
        </div>
      </form>
    </div>
  )
}
