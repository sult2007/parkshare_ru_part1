import { render, screen } from '@testing-library/react';
import SocialLoginButtons from '@/components/auth/SocialLoginButtons';

describe('SocialLoginButtons', () => {
  it('renders provider buttons', () => {
    render(<SocialLoginButtons />);
    expect(screen.getByText(/Sign in with Google/i)).toBeInTheDocument();
    expect(screen.getByText(/Continue with VK/i)).toBeInTheDocument();
    expect(screen.getByText(/Yandex ID/i)).toBeInTheDocument();
  });
});
