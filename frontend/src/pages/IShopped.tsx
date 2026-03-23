import { useState } from 'react'
import PageContainer from '../components/layout/PageContainer'
import PageTitle from '../components/ui/PageTitle'
import ModeSelector, { type ModeType } from '../components/shopped/ModeSelector'
import ScanReceiptTab from '../components/shopped/ScanReceiptTab'
import FromListTab from '../components/shopped/FromListTab'

/**
 * IShopped page - Bulk grocery→inventory conversion flow
 *
 * Features:
 * - Three modes: Scan receipt (coming soon) | From list (functional) | Add manually (coming soon)
 * - Default mode: Scan receipt with fallback to From list
 * - From list: Shows grocery items with storage location selection and bulk confirm
 * - Success flow: Add items to inventory, navigate to pantry
 */
export default function IShopped() {
  const [activeMode, setActiveMode] = useState<ModeType>('scan')

  const handleSwitchToList = () => {
    setActiveMode('list')
  }

  return (
    <PageContainer>
      <div className="py-6">
        <PageTitle>I Shopped</PageTitle>
        <p className="text-text-secondary mb-6">
          Add purchased items to your pantry
        </p>

        {/* Mode selector tabs */}
        <ModeSelector activeMode={activeMode} onModeChange={setActiveMode} />

        {/* Tab content */}
        {activeMode === 'scan' && <ScanReceiptTab onSwitchToList={handleSwitchToList} />}
        {activeMode === 'list' && <FromListTab />}
        {activeMode === 'manual' && (
          <div className="flex flex-col items-center justify-center py-12 px-6">
            <h2 className="text-xl font-medium text-text-primary mb-2 text-center">
              Manual entry coming soon
            </h2>
            <p className="text-sm text-text-secondary text-center max-w-md">
              For now, use your grocery list to add items to your pantry.
            </p>
          </div>
        )}
      </div>
    </PageContainer>
  )
}
