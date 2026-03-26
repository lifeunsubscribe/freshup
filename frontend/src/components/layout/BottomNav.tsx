import { Link, useLocation } from 'react-router-dom'
import { Home, Calendar, ChefHat, UtensilsCrossed, ShoppingCart } from 'lucide-react'
import { useGroceryList } from '../../api'

interface NavItem {
  to: string
  icon: typeof Home
  label: string
  badge?: number
}

export default function BottomNav() {
  const location = useLocation()

  // Fetch unpurchased grocery items for badge count
  const { data: unpurchasedItems = [] } = useGroceryList({
    purchased: false,
  })

  const navItems: NavItem[] = [
    { to: '/', icon: Home, label: 'Home' },
    { to: '/plan', icon: Calendar, label: 'Plan' },
    { to: '/recipes', icon: ChefHat, label: 'Recipes' },
    { to: '/pantry', icon: UtensilsCrossed, label: 'Pantry' },
    { to: '/grocery', icon: ShoppingCart, label: 'List', badge: unpurchasedItems.length },
  ]

  /**
   * Determines if a navigation item should be marked as active.
   * Home route (/) uses exact match to avoid false positives.
   * Other routes use startsWith to catch nested routes (e.g., /recipes/:id activates Recipes tab).
   */
  const isActive = (path: string) => {
    if (path === '/') {
      return location.pathname === '/'
    }
    return location.pathname.startsWith(path)
  }

  return (
    <nav aria-label="Main navigation" className="fixed bottom-0 left-0 right-0 bg-white border-t border-warm-border">
      <div className="flex justify-around items-center h-16 max-w-screen-lg mx-auto">
        {navItems.map((item) => {
          const Icon = item.icon
          const active = isActive(item.to)

          return (
            <Link
              key={item.to}
              to={item.to}
              className="flex flex-col items-center justify-center flex-1 h-full relative"
              aria-current={active ? 'page' : undefined}
            >
              <div className="relative">
                <Icon
                  size={22}
                  className={
                    active
                      ? 'text-olive fill-olive stroke-2'
                      : 'text-text-secondary stroke-2'
                  }
                />
                {item.badge !== undefined && item.badge > 0 && (
                  <span className="absolute -top-1 -right-1 bg-mocha text-cream text-tiny font-medium rounded-full w-4 h-4 flex items-center justify-center">
                    {item.badge}
                  </span>
                )}
              </div>
              <span
                className={`text-tiny mt-1 ${
                  active
                    ? 'text-olive font-medium'
                    : 'text-text-secondary font-normal'
                }`}
              >
                {item.label}
              </span>
            </Link>
          )
        })}
      </div>
    </nav>
  )
}
