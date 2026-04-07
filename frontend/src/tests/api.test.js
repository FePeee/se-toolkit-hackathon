/**
 * Tests for the API client module.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { api } from '../api/client'

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

describe('API Client', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('register', () => {
    it('should send POST request to /api/auth/register', async () => {
      const mockResponse = { access_token: 'token123', user: { id: 1, name: 'Test' } }
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      })

      const result = await api.register('test@test.com', 'password', 'Test User')

      expect(global.fetch).toHaveBeenCalledWith(
        `${BASE}/api/auth/register`,
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ email: 'test@test.com', password: 'password', name: 'Test User' }),
        })
      )
      expect(result).toEqual(mockResponse)
    })
  })

  describe('login', () => {
    it('should send POST request to /api/auth/login with FormData', async () => {
      const mockResponse = { access_token: 'token456', user: { id: 1, name: 'User' } }
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      })

      const result = await api.login('user@test.com', 'secretpass')

      expect(global.fetch).toHaveBeenCalledWith(
        `${BASE}/api/auth/login`,
        expect.objectContaining({ method: 'POST' })
      )
      expect(result).toEqual(mockResponse)
    })

    it('should throw error on failed login', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 400,
      })

      await expect(api.login('wrong@test.com', 'wrongpass'))
        .rejects.toThrow('Invalid credentials')
    })
  })

  describe('authenticated requests', () => {
    it('should include Authorization header when token exists', async () => {
      localStorage.setItem('token', 'mytoken')
      const mockData = { id: 1, name: 'User' }
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockData),
      })

      await api.me()

      expect(global.fetch).toHaveBeenCalledWith(
        `${BASE}/api/auth/me`,
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: 'Bearer mytoken',
          }),
        })
      )
    })

    it('should not include Authorization header when no token', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve([]),
      })

      await api.getHabits()

      expect(global.fetch).toHaveBeenCalledWith(
        `${BASE}/api/habits`,
        expect.objectContaining({
          headers: { 'Content-Type': 'application/json' },
        })
      )
    })
  })

  describe('habits CRUD', () => {
    beforeEach(() => {
      localStorage.setItem('token', 'testtoken')
    })

    it('should create a habit with reminder time', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ id: 1, name: 'Running', reminder_time: '08:00' }),
      })

      const result = await api.createHabit('Running', '08:00')

      expect(global.fetch).toHaveBeenCalledWith(
        `${BASE}/api/habits`,
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ name: 'Running', reminder_time: '08:00' }),
        })
      )
      expect(result.name).toBe('Running')
    })

    it('should create a habit without reminder time', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ id: 1, name: 'Meditation', reminder_time: null }),
      })

      await api.createHabit('Meditation')

      expect(global.fetch).toHaveBeenCalledWith(
        `${BASE}/api/habits`,
        expect.objectContaining({
          body: JSON.stringify({ name: 'Meditation', reminder_time: null }),
        })
      )
    })

    it('should complete a habit', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ message: 'Completed!', streak: 5 }),
      })

      const result = await api.completeHabit(42)

      expect(global.fetch).toHaveBeenCalledWith(
        `${BASE}/api/habits/42/complete`,
        expect.objectContaining({ method: 'POST' })
      )
      expect(result.streak).toBe(5)
    })

    it('should delete a habit', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ message: 'Deleted' }),
      })

      await api.deleteHabit(10)

      expect(global.fetch).toHaveBeenCalledWith(
        `${BASE}/api/habits/10`,
        expect.objectContaining({ method: 'DELETE' })
      )
    })

    it('should throw error when API request fails', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        json: () => Promise.resolve({ detail: 'Habit not found' }),
      })

      await expect(api.deleteHabit(999))
        .rejects.toThrow('Habit not found')
    })
  })
})
