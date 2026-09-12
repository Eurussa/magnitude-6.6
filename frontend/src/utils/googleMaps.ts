import type { TripItem } from '../api/client'

function coordinates(item: TripItem) {
  return `${item.latitude},${item.longitude}`
}

export function createDailyMapUrls(items: TripItem[], embedApiKey: string) {
  const [origin, ...remaining] = items
  if (!origin) return null

  if (remaining.length === 0) {
    const embed = new URL('https://www.google.com/maps/embed/v1/place')
    embed.searchParams.set('key', embedApiKey)
    embed.searchParams.set('q', coordinates(origin))

    const external = new URL('https://www.google.com/maps/search/')
    external.searchParams.set('api', '1')
    external.searchParams.set('query', coordinates(origin))
    return { embedUrl: embed.toString(), externalUrl: external.toString(), isSinglePlace: true }
  }

  const destination = remaining.at(-1)
  if (!destination) return null
  const waypoints = remaining.slice(0, -1)

  const embed = new URL('https://www.google.com/maps/embed/v1/directions')
  embed.searchParams.set('key', embedApiKey)
  embed.searchParams.set('origin', coordinates(origin))
  embed.searchParams.set('destination', coordinates(destination))
  if (waypoints.length > 0) embed.searchParams.set('waypoints', waypoints.map(coordinates).join('|'))

  const external = new URL('https://www.google.com/maps/dir/')
  external.searchParams.set('api', '1')
  external.searchParams.set('origin', coordinates(origin))
  external.searchParams.set('destination', coordinates(destination))
  if (waypoints.length > 0) external.searchParams.set('waypoints', waypoints.map(coordinates).join('|'))
  return { embedUrl: embed.toString(), externalUrl: external.toString(), isSinglePlace: false }
}
