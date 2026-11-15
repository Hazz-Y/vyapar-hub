import { BrowserRouter, Routes, Route, NavLink } from 'react-router'
import { AppProvider, useApp } from './context/AppContext'
import { createApi } from './api/client'
import { ApprovalHost } from './components/ApprovalSheet'
import DemoBar, { DEMO_MODE } from './components/DemoBar'
import Soundbox from './components/Soundbox'
import StatusBar from './components/StatusBar'
import ToolTrace from './components/ToolTrace'
import Home from './pages/Home'
import CashRadar from './pages/CashRadar'
import Udhaar from './pages/Udhaar'
import Suppliers from './pages/Suppliers'
import Growth from './pages/Growth'
import Settings from './pages/Settings'

const MERCHANT_ID = 1
const api = createApi(MERCHANT_ID)

const NAV = [
  { to: '/', label: 'Ghar', icon: '🏠' },
  { to: '/cash', label: 'Cash', icon: '💰' },
  { to: '/udhaar', label: 'Udhaar', icon: '📋' },
  { to: '/suppliers', label: 'Supplier', icon: '🏪' },
  { to: '/growth', label: 'Growth', icon: '📈' },
]

function Shell() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-start bg-slate-100 lg:flex-row lg:items-start lg:justify-center lg:gap-6 lg:py-8 lg:px-4">
      {/* Phone frame */}
      <div className="relative flex h-dvh w-full max-w-[390px] flex-col overflow-hidden bg-slate-50 shadow-none lg:h-[812px] lg:max-h-[812px] lg:rounded-[2.5rem] lg:border-[10px] lg:border-slate-800 lg:shadow-2xl">
        {/* Top App Header with Paytm Logo */}
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-2.5 shrink-0">
          <div className="flex items-center gap-2">
            <img src="/paytm-logo.png" alt="Paytm" className="h-6 w-auto object-contain" />
            <span className="rounded bg-[#00B9F1]/15 px-2 py-0.5 text-[10px] font-bold tracking-wide text-navy uppercase">
              Vyapar Hub
            </span>
          </div>
          <span className="text-[11px] font-medium text-slate-500">
            Kirana Store
          </span>
        </header>

        <StatusBar />
        <main className="flex-1 overflow-y-auto">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/cash" element={<CashRadar />} />
            <Route path="/udhaar" element={<Udhaar />} />
            <Route path="/suppliers" element={<Suppliers />} />
            <Route path="/growth" element={<Growth />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </main>

        <nav
          className="flex shrink-0 border-t border-slate-200 bg-white"
          aria-label="Main navigation"
        >
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.to === '/'}
              className={({ isActive }) =>
                `flex flex-1 flex-col items-center py-2.5 text-[11px] font-medium transition-colors ${
                  isActive ? 'text-[#00B9F1]' : 'text-slate-500 hover:text-slate-700'
                }`
              }
            >
              <span className="text-[20px] leading-tight">{n.icon}</span>
              {n.label}
            </NavLink>
          ))}
          <NavLink
            to="/settings"
            className={({ isActive }) =>
              `flex flex-1 flex-col items-center py-2.5 text-[11px] font-medium transition-colors ${
                isActive ? 'text-[#00B9F1]' : 'text-slate-500 hover:text-slate-700'
              }`
            }
          >
            <span className="text-[20px] leading-tight">⚙️</span>
            Settings
          </NavLink>
        </nav>

        {/* Approval sheet overlays the phone frame */}
        <ApprovalHost useAppHook={useApp} />
      </div>

      {/* Desktop sidebar: Soundbox + Tool Trace */}
      <aside className={`${DEMO_MODE ? 'order-first flex w-full justify-center p-2 lg:order-none lg:p-0' : 'hidden'} shrink-0 lg:block lg:w-72 lg:space-y-4`}>
        {DEMO_MODE && <DemoBar />}
        <div className="hidden rounded-2xl bg-slate-900 p-4 lg:block">
          <div className="mb-3 flex items-center justify-between">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
              Paytm Soundbox
            </p>
            <img src="/paytm-logo.png" alt="Paytm" className="h-4 w-auto brightness-0 invert opacity-80" />
          </div>
          <Soundbox />
        </div>
        <div className="hidden lg:block">
          <ToolTrace />
        </div>
      </aside>
    </div>
  )
}

export default function App() {
  return (
    <AppProvider merchantId={MERCHANT_ID} api={api}>
      <BrowserRouter>
        <Shell />
      </BrowserRouter>
    </AppProvider>
  )
}
