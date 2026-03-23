interface SectionNavProps {
  sections: Array<{ id: string; label: string }>
}

/**
 * SectionNav displays a sticky horizontal navigation bar
 *
 * Features:
 * - Sticky positioning below search bar
 * - Horizontal scroll for navigation links
 * - Smooth scroll to section when clicked
 * - Active section highlighting (future enhancement)
 */
export default function SectionNav({ sections }: SectionNavProps) {
  const scrollToSection = (sectionId: string) => {
    const element = document.getElementById(sectionId)
    if (element) {
      // Scroll with offset to account for sticky nav
      const offset = 120 // Account for nav height + padding
      const elementPosition = element.getBoundingClientRect().top
      const offsetPosition = elementPosition + window.scrollY - offset

      window.scrollTo({
        top: offsetPosition,
        behavior: 'smooth',
      })
    }
  }

  return (
    <nav className="sticky top-0 z-10 bg-cream-light border-b border-warm-border py-2 -mx-4 px-4">
      <div className="flex gap-3 overflow-x-auto scrollbar-hide">
        {sections.map((section) => (
          <button
            key={section.id}
            onClick={() => scrollToSection(section.id)}
            className="flex-shrink-0 px-3 py-1.5 text-sm text-text-secondary hover:text-text-primary hover:bg-warm-gray rounded-md transition-colors whitespace-nowrap"
          >
            {section.label}
          </button>
        ))}
      </div>
    </nav>
  )
}
