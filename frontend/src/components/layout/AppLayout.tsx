import { useState, type ReactNode } from 'react';
import { Menu, X } from 'lucide-react';
import Sidebar from './Sidebar';
import TopHeader from './TopHeader';

interface AppLayoutProps {
  children: ReactNode;
  title: string;
  subtitle: string;
  experimentCode?: string | null;
  experimentTitle?: string | null;
}

export default function AppLayout({
  children,
  title,
  subtitle,
  experimentCode,
  experimentTitle,
}: AppLayoutProps) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  return (
    <div className="h-screen flex flex-col bg-[#f6f1ec] text-[#261912] font-sans">
      {/* Mobile nav toggle */}
      <div className="md:hidden flex items-center justify-between px-3 h-12 bg-[#ede5dc] border-b border-[#ded2c5]">
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono font-bold text-[#261912] tracking-widest uppercase">
            AEGIS-BAS // MISSION CONTROL
          </span>
        </div>
        <button
          onClick={() => setMobileNavOpen(!mobileNavOpen)}
          className="p-1.5 rounded hover:bg-[#e4d7ca] text-space-400"
          aria-label="Toggle navigation menu"
        >
          {mobileNavOpen ? <X className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
        </button>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Desktop sidebar */}
        <div className="hidden md:block">
          <Sidebar />
        </div>

        {/* Mobile sidebar overlay */}
        {mobileNavOpen && (
          <div className="md:hidden fixed inset-0 z-50 flex">
            <div className="w-60 h-full">
              <Sidebar />
            </div>
            <div
              className="flex-1 bg-black/40"
              onClick={() => setMobileNavOpen(false)}
            />
          </div>
        )}

        {/* Main operational console area */}
        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="hidden md:block">
            <TopHeader
              title={title}
              subtitle={subtitle}
              experimentCode={experimentCode}
              experimentTitle={experimentTitle}
            />
          </div>
          <main role="main" className="flex-1 overflow-y-auto p-3 sm:p-4">
            {children}
          </main>
        </div>
      </div>
    </div>
  );
}
