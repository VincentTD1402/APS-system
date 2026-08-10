
export interface DragScrollOptions {
  scrollEl: HTMLElement
  track: HTMLElement
  thumb: HTMLElement
  axis: 'x' | 'y'
  pad?: number          // gutter inside track (hscroll only)
  syncPartner?: HTMLElement // element whose scrollTop is kept in sync (fixed-side for vscroll)
}

/**
 * Reusable custom scrollbar composable.
 * Wires thumb drag, track page-jump, wheel forwarding, and resize-driven thumb sizing.
 * Call from onMounted after refs are guaranteed to be HTMLElements.
 */
export function useDragScroll(opts: DragScrollOptions): { update: () => void; cleanup: () => void } {
  const { scrollEl, track, thumb, axis, pad = 0, syncPartner } = opts

  function update() {
    if (axis === 'x') {
      const view = scrollEl.clientWidth
      const cont = scrollEl.scrollWidth
      const trackW = track.clientWidth - pad * 2
      if (cont <= view) { thumb.style.display = 'none'; return }
      thumb.style.display = 'block'
      const w = Math.max(24, trackW * (view / cont))
      thumb.style.width = w + 'px'
      const scrollable = cont - view
      const trackable  = trackW - w
      thumb.style.left = (pad + (scrollable > 0 ? (scrollEl.scrollLeft / scrollable) * trackable : 0)) + 'px'
    } else {
      const view = scrollEl.clientHeight
      const cont = scrollEl.scrollHeight
      const trackH = track.clientHeight
      if (cont <= view) { thumb.style.display = 'none'; return }
      thumb.style.display = 'block'
      const h = Math.max(24, trackH * (view / cont))
      thumb.style.height = h + 'px'
      const scrollable = cont - view
      const trackable  = trackH - h
      thumb.style.top = (scrollable > 0 ? (scrollEl.scrollTop / scrollable) * trackable : 0) + 'px'
    }
  }

  // Drag state
  let dragging = false
  let startPos = 0
  let startScroll = 0

  function onThumbMousedown(e: MouseEvent) {
    dragging = true
    startPos = axis === 'x' ? e.clientX : e.clientY
    startScroll = axis === 'x' ? scrollEl.scrollLeft : scrollEl.scrollTop
    e.preventDefault()
  }

  function onDocMousemove(e: MouseEvent) {
    if (!dragging) return
    const trackSize = (axis === 'x' ? track.clientWidth  : track.clientHeight) - pad * 2
    const thumbSize = axis === 'x' ? thumb.clientWidth  : thumb.clientHeight
    const contSize  = axis === 'x' ? scrollEl.scrollWidth  : scrollEl.scrollHeight
    const viewSize  = axis === 'x' ? scrollEl.clientWidth  : scrollEl.clientHeight
    const scrollable = contSize - viewSize
    const trackable  = trackSize - thumbSize
    if (trackable <= 0) return
    const delta = (axis === 'x' ? e.clientX : e.clientY) - startPos
    const newScroll = startScroll + (delta / trackable) * scrollable
    if (axis === 'x') scrollEl.scrollLeft = newScroll
    else              scrollEl.scrollTop  = newScroll
  }

  function onDocMouseup() {
    dragging = false
  }

  function onTrackMousedown(e: MouseEvent) {
    if (e.target === thumb) return
    const rect = track.getBoundingClientRect()
    if (axis === 'x') {
      const click = e.clientX - rect.left
      const thumbStart = thumb.offsetLeft
      const thumbLen   = thumb.clientWidth
      const dir = click < thumbStart + thumbLen / 2 ? -1 : 1
      scrollEl.scrollLeft += dir * scrollEl.clientWidth * 0.8
    } else {
      const click = e.clientY - rect.top
      const thumbStart = thumb.offsetTop
      const thumbLen   = thumb.clientHeight
      const dir = click < thumbStart + thumbLen / 2 ? -1 : 1
      scrollEl.scrollTop += dir * scrollEl.clientHeight * 0.8
    }
  }

  function onScroll() {
    if (syncPartner && axis === 'y') {
      syncPartner.scrollTop = scrollEl.scrollTop
    }
    update()
  }

  function onResize() { update() }

  thumb.addEventListener('mousedown', onThumbMousedown)
  document.addEventListener('mousemove', onDocMousemove)
  document.addEventListener('mouseup', onDocMouseup)
  track.addEventListener('mousedown', onTrackMousedown)
  scrollEl.addEventListener('scroll', onScroll)
  window.addEventListener('resize', onResize)

  // Observe scrollEl + its content — catches late layout (tables rendering, fonts loading)
  let ro: ResizeObserver | null = null
  if (typeof ResizeObserver !== 'undefined') {
    ro = new ResizeObserver(update)
    ro.observe(scrollEl)
    if (scrollEl.firstElementChild) ro.observe(scrollEl.firstElementChild)
  }

  update()
  // Retries for late layout (font load, image decode, etc.)
  requestAnimationFrame(update)
  setTimeout(update, 100)
  setTimeout(update, 500)

  function cleanup() {
    thumb.removeEventListener('mousedown', onThumbMousedown)
    document.removeEventListener('mousemove', onDocMousemove)
    document.removeEventListener('mouseup', onDocMouseup)
    track.removeEventListener('mousedown', onTrackMousedown)
    scrollEl.removeEventListener('scroll', onScroll)
    window.removeEventListener('resize', onResize)
    ro?.disconnect()
  }

  return { update, cleanup }
}
