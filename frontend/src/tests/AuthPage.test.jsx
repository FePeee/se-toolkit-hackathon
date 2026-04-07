/**
 * Tests for AuthPage component.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import AuthPage from '../pages/AuthPage'

describe('AuthPage', () => {
  const mockOnLogin = vi.fn()

  beforeEach(() => {
    mockOnLogin.mockClear()
    localStorage.clear()
  })

  it('renders login form by default', () => {
    render(<AuthPage onLogin={mockOnLogin} />)

    expect(screen.getByPlaceholderText('Email')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Password')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument()
    expect(screen.queryByPlaceholderText('Your name')).not.toBeInTheDocument()
  })

  it('switches to register mode when clicking Register link', async () => {
    const user = userEvent.setup()
    render(<AuthPage onLogin={mockOnLogin} />)

    const registerLink = screen.getByText('Register')
    await user.click(registerLink)

    expect(screen.getByPlaceholderText('Your name')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /create account/i })).toBeInTheDocument()
    expect(screen.getByText(/already have one/i)).toBeInTheDocument()
  })

  it('switches back to login mode when clicking Sign in link', async () => {
    const user = userEvent.setup()
    render(<AuthPage onLogin={mockOnLogin} />)

    await user.click(screen.getByText('Register'))
    expect(screen.getByPlaceholderText('Your name')).toBeInTheDocument()

    await user.click(screen.getByText('Sign in'))
    expect(screen.queryByPlaceholderText('Your name')).not.toBeInTheDocument()
  })

  it('calls onLogin with user data after successful registration', async () => {
    const user = userEvent.setup()
    const mockResponse = {
      access_token: 'testtoken123',
      user: { id: 1, email: 'test@test.com', name: 'Test User' },
    }

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockResponse),
    })

    render(<AuthPage onLogin={mockOnLogin} />)

    // Switch to register
    await user.click(screen.getByText('Register'))

    // Fill form
    await user.type(screen.getByPlaceholderText('Your name'), 'Test User')
    await user.type(screen.getByPlaceholderText('Email'), 'test@test.com')
    await user.type(screen.getByPlaceholderText('Password'), 'password123')

    // Submit
    await user.click(screen.getByRole('button', { name: /create account/i }))

    // Wait for async operation
    await vi.waitFor(() => {
      expect(mockOnLogin).toHaveBeenCalledWith(mockResponse.user)
    })
    expect(localStorage.getItem('token')).toBe('testtoken123')
  })

  it('calls onLogin with user data after successful login', async () => {
    const user = userEvent.setup()
    const mockResponse = {
      access_token: 'logintoken',
      user: { id: 2, email: 'user@test.com', name: 'Login User' },
    }

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockResponse),
    })

    render(<AuthPage onLogin={mockOnLogin} />)

    await user.type(screen.getByPlaceholderText('Email'), 'user@test.com')
    await user.type(screen.getByPlaceholderText('Password'), 'password')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    await vi.waitFor(() => {
      expect(mockOnLogin).toHaveBeenCalledWith(mockResponse.user)
    })
    expect(localStorage.getItem('token')).toBe('logintoken')
  })

  it('displays error message on failed request', async () => {
    const user = userEvent.setup()

    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({ detail: 'Invalid credentials' }),
    })

    render(<AuthPage onLogin={mockOnLogin} />)

    await user.type(screen.getByPlaceholderText('Email'), 'wrong@test.com')
    await user.type(screen.getByPlaceholderText('Password'), 'wrongpass')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    await vi.waitFor(() => {
      expect(screen.getByText('Invalid credentials')).toBeInTheDocument()
    })
  })

  it('shows loading state during submission', async () => {
    const user = userEvent.setup()

    // Mock a slow response
    global.fetch = vi.fn().mockImplementation(() =>
      new Promise(resolve =>
        setTimeout(
          () => resolve({ ok: true, json: () => Promise.resolve({ access_token: 't', user: {} }) }),
          100
        )
      )
    )

    render(<AuthPage onLogin={mockOnLogin} />)

    await user.type(screen.getByPlaceholderText('Email'), 'test@test.com')
    await user.type(screen.getByPlaceholderText('Password'), 'pass')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    expect(screen.getByRole('button', { name: /loading/i })).toBeDisabled()
  })
})
