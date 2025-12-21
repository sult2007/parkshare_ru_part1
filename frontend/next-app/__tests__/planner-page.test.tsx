import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import PlannerPage from '@/app/(site)/planner/page';
import * as authHook from '@/hooks/useAuth';
import * as plannerClient from '@/lib/plannerClient';

describe('PlannerPage', () => {
  it('prompts login when unauthenticated', () => {
    jest.spyOn(authHook, 'useAuth').mockReturnValue({
      isAuthenticated: false,
      user: null,
      loading: false,
      logout: jest.fn()
    } as any);

    render(<PlannerPage />);

    expect(screen.getByText(/Войдите, чтобы планировать парковку/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Войти/i })).toHaveAttribute('href', '/auth');
  });

  it('submits payload and renders recommendations when authenticated', async () => {
    jest.spyOn(authHook, 'useAuth').mockReturnValue({
      isAuthenticated: true,
      user: { id: '1' },
      loading: false,
      logout: jest.fn()
    } as any);

    jest.spyOn(plannerClient, 'planParking').mockResolvedValue({
      recommendations: [
        { spot_id: '1', lot_name: 'Лот', address: 'Адрес', distance_km: 0.5, predicted_occupancy: 0.2, has_ev_charging: true, is_covered: false, hourly_price: 100, confidence: 0.8 }
      ]
    });

    render(<PlannerPage />);

    fireEvent.submit(screen.getByRole('button', { name: /Получить план/i }));

    await waitFor(() => expect(plannerClient.planParking).toHaveBeenCalled());
    expect(await screen.findByText(/Лот/)).toBeInTheDocument();
    expect(screen.getByText(/Адрес/)).toBeInTheDocument();
  });
});
