import BriefingCard from '../components/BriefingCard'
import AssistantPanel, { DEMO_PHRASES } from '../components/AssistantPanel'

export default function Home() {
  return (
    <div className="space-y-4 p-4 pb-6">
      <BriefingCard />
      <AssistantPanel suggestions={DEMO_PHRASES} />
    </div>
  )
}
