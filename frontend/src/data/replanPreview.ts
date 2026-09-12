import type { Plan, PlanId, ReplanResponse, TripItem } from '../api/client'

function withoutItems(items: TripItem[], itemIds: string[]) {
  return items.filter((item) => !itemIds.includes(item.id))
}

function moveItem(items: TripItem[], itemId: string, scheduledDate: string, startTime: string) {
  return items.map((item) => item.id === itemId
    ? { ...item, scheduled_date: scheduledDate, start_time: startTime }
    : item)
}

function withPreview(plan: Plan, items: TripItem[], explanation: string): Plan {
  return { ...plan, items, feasible: false, explanation }
}

function delayPreview(plans: Plan[], items: TripItem[]) {
  const firstMorningItem = items.find((item) => item.id === 'item-1')
  const museum = items.find((item) => item.id === 'item-2')
  const nextDate = [...new Set(items.map((item) => item.scheduled_date))].sort()[1]
  const previewById: Record<PlanId, { items: TripItem[]; explanation: string }> = {
    A: {
      items: firstMorningItem ? withoutItems(items, [firstMorningItem.id]) : items,
      explanation: '先放棄已錯過的第一個景點，午餐、teamLab 和晚餐維持原定時間。',
    },
    B: {
      items: firstMorningItem && nextDate ? moveItem(items, firstMorningItem.id, nextDate, '18:30') : items,
      explanation: '今天從博物館開始，把早上錯過的景點移到隔天傍晚，盡量保留完整旅程。',
    },
    C: {
      items: withoutItems(items, [firstMorningItem?.id, museum?.id].filter((id): id is string => Boolean(id))),
      explanation: '上午留白休息，從午餐開始接回原行程，避免後續一路趕場。',
    },
  }
  return plans.map((plan) => withPreview(plan, previewById[plan.id].items, previewById[plan.id].explanation))
}

function rainPreview(plans: Plan[], items: TripItem[]) {
  const disney = items.find((item) => item.name.includes('迪士尼'))
  const dates = [...new Set(items.map((item) => item.scheduled_date))].sort()
  const swapDate = disney ? dates[dates.indexOf(disney.scheduled_date) - 1] : undefined
  const swappedItems = disney && swapDate
    ? items.map((item) => {
        if (item.scheduled_date === disney.scheduled_date) return { ...item, scheduled_date: swapDate }
        if (item.scheduled_date === swapDate) return { ...item, scheduled_date: disney.scheduled_date }
        return item
      })
    : items
  const previewById: Record<PlanId, { items: TripItem[]; explanation: string }> = {
    A: { items: swappedItems, explanation: '把迪士尼與前一天行程對調，避開高降雨機率，同時保留其他安排。' },
    B: { items: swappedItems, explanation: '交換兩天的完整內容，保留所有景點，再依當天動線調整出發時間。' },
    C: { items, explanation: '暫時保留原日期，行程不提前搬動；出發前再依最新天氣決定。' },
  }
  return plans.map((plan) => withPreview(plan, previewById[plan.id].items, previewById[plan.id].explanation))
}

function closurePreview(plans: Plan[], items: TripItem[]) {
  const museum = items.find((item) => item.name.includes('博物館'))
  const nextDate = [...new Set(items.map((item) => item.scheduled_date))].sort()[1]
  const withoutMuseum = museum ? withoutItems(items, [museum.id]) : items
  const previewById: Record<PlanId, { items: TripItem[]; explanation: string }> = {
    A: { items: withoutMuseum, explanation: '移除臨時休館的景點，其他預約與時間維持不變。' },
    B: {
      items: museum && nextDate ? moveItem(items, museum.id, nextDate, '18:30') : withoutMuseum,
      explanation: '把休館景點移到隔天傍晚，先保留參觀機會，再確認重新開放時間。',
    },
    C: { items: withoutMuseum, explanation: '取消休館景點並保留空檔，今天不另外塞入新的行程。' },
  }
  return plans.map((plan) => withPreview(plan, previewById[plan.id].items, previewById[plan.id].explanation))
}

export function buildPreviewPlans(result: ReplanResponse) {
  const items = result.plans[0]?.items ?? []
  const message = result.event.summary
  if (/雨|天氣|颱風/.test(message)) return rainPreview(result.plans, items)
  if (/休館|關閉|沒開/.test(message)) return closurePreview(result.plans, items)
  return delayPreview(result.plans, items)
}
