import { Sidebar } from '@/components/Sidebar'
import { FloatingAssistant } from '@/components/FloatingAssistant'

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 overflow-auto bg-background">
        {children}
      </main>
      <FloatingAssistant />
    </div>
  )
}
