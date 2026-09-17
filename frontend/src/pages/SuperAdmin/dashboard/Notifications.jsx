import { useState } from 'react';
import Card from '../../../components/ui/Card.jsx';
import Badge from '../../../components/ui/Badge.jsx';
import Button from '../../../components/ui/Button.jsx';
import DashboardPageShell from './DashboardPageShell.jsx';
import { useDashboardData } from './useDashboardData.js';
import { EmptyState, formatRelativeTime } from './dashboardHelpers.jsx';
import { api } from '../../../lib/api.js';

const ENDPOINTS = { notifications: '/notifications/?page_size=20' };

export default function SuperAdminNotifications() {
  const { data, loading, error, reload } = useDashboardData(ENDPOINTS);
  const notifications = data?.notifications || [];
  const [marking, setMarking] = useState(false);

  const markAllRead = async () => {
    setMarking(true);
    try {
      await api.post('/notifications/read-all', {});
      reload();
    } finally {
      setMarking(false);
    }
  };

  const markOneRead = async (id) => {
    await api.post(`/notifications/${id}/read`, {});
    reload();
  };

  return (
    <DashboardPageShell
      pageTitle="Notifications"
      title="Notifications"
      subtitle="Notifications addressed to your account."
      loading={loading}
      error={error}
      onReload={reload}
      skeletonCount={1}
    >
      {data && (
        <Card padding={notifications.length ? 'none' : 'lg'}>
          {notifications.some((n) => !n.is_read) && (
            <div className="flex justify-end px-lg pt-lg">
              <Button variant="secondary" size="sm" onClick={markAllRead} disabled={marking}>Mark All Read</Button>
            </div>
          )}
          {notifications.length === 0 ? (
            <EmptyState icon="notifications" text="No data available yet" />
          ) : (
            <ul className="divide-y divide-outline/10">
              {notifications.map((notification) => (
                <li
                  key={notification.id}
                  className={`flex items-start gap-md px-lg py-md cursor-pointer transition-colors hover:bg-surface-container-low ${notification.is_read ? '' : 'bg-primary-container/10'}`}
                  onClick={() => !notification.is_read && markOneRead(notification.id)}
                >
                  <span className="material-symbols-outlined text-secondary shrink-0 mt-0.5">
                    {notification.is_read ? 'notifications' : 'notifications_active'}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-start justify-between gap-sm">
                      <p className="font-body-md text-body-md font-bold text-on-surface">{notification.title}</p>
                      {!notification.is_read && <Badge tone="secondary">New</Badge>}
                    </div>
                    <p className="font-body-md text-body-md text-on-surface-variant">{notification.body}</p>
                    <p className="font-label-sm text-label-sm text-outline mt-0.5">{formatRelativeTime(notification.created_at)}</p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}
    </DashboardPageShell>
  );
}
