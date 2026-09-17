import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getNotificationsPath, getPortal } from '../../config/portals.js';
import usePageTitle from '../../hooks/usePageTitle.js';
import { useBranding } from '../../context/BrandingContext.jsx';
import { useAuth } from '../../context/AuthContext.jsx';
import { useUIPreferences, SIDEBAR_COLLAPSED_WIDTH } from '../../context/UIPreferences.jsx';
import { useApplyAppearance } from '../../hooks/useApplyAppearance.js';
import { api } from '../../lib/api.js';
import TopHeader from './TopHeader.jsx';
import Sidebar from './Sidebar.jsx';
import BottomNav from './BottomNav.jsx';

/**
 * Shared portal shell: top header, desktop sidebar, mobile bottom nav,
 * driven entirely by the per-portal nav config in src/config/portals.js
 * so nav items can't drift out of sync again. Active-state highlighting
 * is resolved by react-router's <NavLink> against the current route.
 */
export default function AppShell({ portalId, pageTitle, children }) {
  const portal = getPortal(portalId);
  const navigate = useNavigate();
  const { logout } = useAuth();
  const { branding } = useBranding();
  const { isDark, sidebarWidth, sidebarCollapsed } = useUIPreferences();
  const sidebarPx = sidebarCollapsed ? SIDEBAR_COLLAPSED_WIDTH : sidebarWidth;
  useApplyAppearance();
  usePageTitle(pageTitle || portal.label);

  // Fetched once per shell mount (fresh on every login/full page load, per
  // spec) — not polled, so it won't reflect a notification that arrives or
  // gets read without a reload/re-navigation. notificationsPath is null for
  // the few portals (admin, classTeacher, examOfficer, libraryAttendant)
  // with no Messages/Communication page of their own yet; the bell stays
  // inert there rather than guessing a destination.
  const [unreadCount, setUnreadCount] = useState(0);
  const notificationsPath = getNotificationsPath(portalId);
  useEffect(() => {
    api.get('/notifications/unread-count')
      .then((res) => setUnreadCount(res.unread_count || 0))
      .catch(() => setUnreadCount(0));
  }, []);

  // Real school identity (General settings) wins over the static per-portal
  // fallback — this is what makes editing the school name/logo actually
  // show up in the chrome instead of just being saved to a table. The
  // theme-specific logo is optional per school — falls back to the one
  // default logo when only that's been set.
  const wordmark = branding.short_name || branding.name || portal.brand.wordmark;
  const themedLogo = isDark ? branding.dark_logo : branding.light_logo;
  const brand = { ...portal.brand, wordmark, logoUrl: themedLogo || branding.logo || undefined };

  const handleSignOut = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-background" style={{ '--sidebar-w': `${sidebarPx}px` }}>
      <div className="no-print">
        <TopHeader
          wordmark={wordmark} logoUrl={brand.logoUrl} homePath={portal.homePath} portalId={portalId}
          notificationCount={unreadCount} notificationsPath={notificationsPath}
        />
        <Sidebar items={portal.sidebarNav} brand={brand} onSignOut={handleSignOut} />
      </div>
      <main className="lg:ml-(--sidebar-w) pb-24 lg:pb-xl px-md sm:px-gutter xl:px-xl pt-lg max-w-container-max mx-auto print:ml-0 print:p-0 print:max-w-none transition-[margin-left] duration-200 ease-out">
        {children}
      </main>
      <div className="no-print">
        <BottomNav items={portal.bottomNav} fullNav={portal.sidebarNav} />
      </div>
    </div>
  );
}
