import { useState } from 'react'
import PageContainer from '../components/layout/PageContainer'
import PageTitle from '../components/ui/PageTitle'
import ModeSelector, { type ModeType } from '../components/shopped/ModeSelector'
import ScanReceiptTab from '../components/shopped/ScanReceiptTab'
import FromListTab from '../components/shopped/FromListTab'
import ManualAddTab from '../components/shopped/ManualAddTab'

/**
 * IShopped page - Bulk grocery→inventory conversion flow
 *
 * Features:
 * - Three modes: Scan receipt (coming soon) | From list (functional) | Add manually (functional)
 * - Default mode: Scan receipt with fallback to From list
 * - From list: Shows grocery items with storage location selection and bulk confirm
 * - Add manually: Manual inventory entry form with validation
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
        {activeMode === 'manual' && <ManualAddTab />}
      </div>
    </PageContainer>
  )
}
