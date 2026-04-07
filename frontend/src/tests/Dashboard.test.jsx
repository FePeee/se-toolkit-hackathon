/**
 * Tests for Dashboard component.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Dashboard from '../pages/Dashboard'

describe('Dashboard', () => {
  const mockUser = { id: 1, name: 'Test User', email: 'test@test.com' }
  const mockOnLogout = vi.fn()
  const mockHabits = [
    { id: 1, name: 'Running', reminder_time: '08:00', is_active: true, streak: 5, done_today: false },
    { id: 2, name: 'Meditation', reminder_time: null, is_active: true, streak: 0, done_today: true },
    { id: 3, name: 'Reading', reminder_time: '21:00', is_active: true, streak: 12, done_today: false },
  ]

  beforeEach(() => {
    mockOnLogout.mockClear()
    global.fetch = vi.fn()
  })

  it('renders header with user name', async () => {
    global.fetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([]),
    })

    render(<Dashboard user={mockUser} onLogout={mockOnLogout} />)

    expect(screen.getByText(/hi, test user/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /logout/i })).toBeInTheDocument()
  })

  it('displays stats row with correct values', async () => {
    global.fetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockHabits),
    })

    render(<Dashboard user={mockUser} onLogout={mockOnLogout} />)

    await waitFor(() => {
      expect(screen.getByText('Total habits')).toBeInTheDocument()
      expect(screen.getByText('3')).toBeInTheDocument()
      expect(screen.getByText('Done today')).toBeInTheDocument()
      expect(screen.getByText('1/3')).toBeInTheDocument()
      expect(screen.getByText("Today's rate")).toBeInTheDocument()
      expect(screen.getByText('33%')).toBeInTheDocument()
    })
  })

  it('shows empty state when no habits', async () => {
    global.fetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([]),
    })

    render(<Dashboard user={mockUser} onLogout={mockOnLogout} />)

    await waitFor(() => {
      expect(screen.getByText(/no habits yet/i)).toBeInTheDocument()
    })
  })

  it('renders habits list', async () => {
    global.fetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockHabits),
    })

    render(<Dashboard user={mockUser} onLogout={mockOnLogout} />)

    await waitFor(() => {
      expect(screen.getByText('Running')).toBeInTheDocument()
      expect(screen.getByText('Meditation')).toBeInTheDocument()
      expect(screen.getByText('Reading')).toBeInTheDocument()
    })

    // Check reminder times
    expect(screen.getByText('08:00')).toBeInTheDocument()
    expect(screen.getByText('21:00')).toBeInTheDocument()
  })

  it('marks habit as complete when clicking checkbox', async () => {
    const user = userEvent.setup()
    global.fetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockHabits),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ message: 'Completed!', streak: 6 }),
      })

    render(<Dashboard user={mockUser} onLogout={mockOnLogout} />)

    await waitFor(() => {
      expect(screen.getByText('Running')).toBeInTheDocument()
    })

    const checkboxes = screen.getAllByRole('button')
    const runningCheckbox = checkboxes.find(cb =>
      cb.closest('div')?.querySelector('span')?.textContent === 'Running'
    )

    // Running is not done today, so checkbox should be clickable
    await user.click(screen.getAllByRole('button')[0])

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/habits/1/complete'),
        expect.objectContaining({ method: 'POST' })
      )
    })
  })

  it('shows streak badges for habits with streak > 0', async () => {
    global.fetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockHabits),
    })

    render(<Dashboard user={mockUser} onLogout={mockOnLogout} />)

    await waitFor(() => {
      expect(screen.getByText('✦ 5d')).toBeInTheDocument()
      expect(screen.getByText('🔥 12d')).toBeInTheDocument()
    })
  })

  it('shows telegram link banner when user has link_code', async () => {
    global.fetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([]),
    })

    const userWithCode = { ...mockUser, link_code: '123456' }
    render(<Dashboard user={userWithCode} onLogout={mockOnLogout} />)

    expect(screen.getByText(/link your telegram account/i)).toBeInTheDocument()
    expect(screen.getByText('/start 123456')).toBeInTheDocument()
  })

  it('does not show telegram banner when user has no link_code', async () => {
    global.fetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([]),
    })

    render(<Dashboard user={mockUser} onLogout={mockOnLogout} />)

    expect(screen.queryByText(/link your telegram account/i)).not.toBeInTheDocument()
  })

  it('opens add habit form when clicking + Add habit', async () => {
    const user = userEvent.setup()
    global.fetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([]),
    })

    render(<Dashboard user={mockUser} onLogout={mockOnLogout} />)

    await user.click(screen.getByRole('button', { name: /\+ add habit/i }))

    expect(screen.getByPlaceholderText('Habit name')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /save/i })).toBeInTheDocument()
  })

  it('creates a new habit and adds it to the list', async () => {
    const user = userEvent.setup()
    const newHabit = { id: 99, name: 'Yoga', reminder_time: '07:00', streak: 0, done_today: false }

    global.fetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve([]),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(newHabit),
      })

    render(<Dashboard user={mockUser} onLogout={mockOnLogout} />)

    // Open form
    await user.click(screen.getByRole('button', { name: /\+ add habit/i }))

    // Fill and submit
    await user.type(screen.getByPlaceholderText('Habit name'), 'Yoga')
    await user.click(screen.getByRole('button', { name: /save/i }))

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/habits'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ name: 'Yoga', reminder_time: null }),
        })
      )
    })
  })

  it('calls logout handler when clicking logout', async () => {
    const user = userEvent.setup()
    global.fetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([]),
    })

    render(<Dashboard user={mockUser} onLogout={mockOnLogout} />)

    await user.click(screen.getByRole('button', { name: /logout/i }))

    expect(mockOnLogout).toHaveBeenCalled()
    expect(localStorage.getItem('token')).toBeNull()
  })

  it('shows done_today habits as completed with strikethrough', async () => {
    global.fetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockHabits),
    })

    render(<Dashboard user={mockUser} onLogout={mockOnLogout} />)

    await waitFor(() => {
      const meditation = screen.getByText('Meditation')
      expect(meditation).toHaveStyle('text-decoration: line-through')
    })
  })
})
