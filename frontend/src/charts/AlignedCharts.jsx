import { createContext, useCallback, useContext, useMemo, useState } from 'react'

// Charts stacked in a group share the widest y-axis, so their plots start at the same x and a week sits at the
// same place on each. Outside a group a chart keeps its own axis.
const Group = createContext({ axisWidth: 0, onAxisWidth: () => {} })

export function AlignedCharts({ children }) {
  const [axisWidth, setAxisWidth] = useState(0)
  // Only ever grows, so the charts settle after one pass instead of re-fitting each other.
  const onAxisWidth = useCallback((width) => setAxisWidth((widest) => Math.max(widest, Math.ceil(width))), [])
  const value = useMemo(() => ({ axisWidth, onAxisWidth }), [axisWidth, onAxisWidth])
  return <Group.Provider value={value}>{children}</Group.Provider>
}

export function useAlignedAxis() {
  return useContext(Group)
}
