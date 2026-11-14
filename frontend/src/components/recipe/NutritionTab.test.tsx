import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import NutritionTab from './NutritionTab'

describe('NutritionTab', () => {
  it('shows readable labels for schema.org nutrient keys', () => {
    render(
      <NutritionTab
        nutritionalInfo={{ fatContent: '17 g', saturatedFatContent: '3 g', carbohydrateContent: '75 g' }}
      />
    )
    expect(screen.getByText('Fat')).toBeInTheDocument()
    expect(screen.getByText('Saturated fat')).toBeInTheDocument()
    expect(screen.getByText('Carbohydrates')).toBeInTheDocument()
    expect(screen.queryByText(/Content/)).not.toBeInTheDocument()
    expect(screen.getByText('17 g')).toBeInTheDocument()
  })

  it('orders nutrients like a nutrition label, unknown keys last', () => {
    const { container } = render(
      <NutritionTab
        nutritionalInfo={{ vitaminCContent: '5 mg', proteinContent: '19 g', calories: '510 kcal', fatContent: '17 g' }}
      />
    )
    const labels = Array.from(container.querySelectorAll('span.font-medium')).map((el) => el.textContent)
    expect(labels).toEqual(['Calories', 'Fat', 'Protein', 'Vitamin c'])
  })

  it('shows the empty message when there is no data', () => {
    render(<NutritionTab nutritionalInfo={null} />)
    expect(screen.getByText(/not available/)).toBeInTheDocument()
  })

  it('splits unknown camelCase and snake_case keys into words', () => {
    render(<NutritionTab nutritionalInfo={{ polyunsaturatedFatContent: '2 g', added_sugar: '4 g' }} />)
    expect(screen.getByText('Polyunsaturated fat')).toBeInTheDocument()
    expect(screen.getByText('Added sugar')).toBeInTheDocument()
  })
})
