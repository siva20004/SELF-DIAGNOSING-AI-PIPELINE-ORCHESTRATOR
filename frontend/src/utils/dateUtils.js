/**
 * Centralized Date & Time Utility for Indian Standard Time (IST)
 * ==============================================================
 * Guarantees that all timestamps across Run History, User Audits,
 * Pipeline Results, and Telemetry render in Indian Standard Time (UTC+05:30).
 */

export function formatIST(dateStr) {
  if (!dateStr) return '—';
  try {
    const s = String(dateStr).trim();
    let date;
    if (s.endsWith('Z') || /[+-]\d{2}:?\d{2}$/.test(s)) {
      date = new Date(s);
    } else {
      const iso = s.replace(' ', 'T');
      // If the naive datetime string was recorded on a cloud server/Neon in UTC (e.g. 05:05:34 AM when local IST was 10:35:34 AM),
      // hours 00-07 on today's date represent UTC. Converting as UTC (iso + 'Z') computes the real Indian Standard Time (+05:30).
      const match = iso.match(/T(\d{2}):/);
      if (match && parseInt(match[1], 10) < 8) {
        date = new Date(iso + 'Z');
      } else {
        date = new Date(iso + '+05:30');
      }
    }
    if (isNaN(date.getTime())) return s;

    return (
      date.toLocaleString('en-IN', {
        timeZone: 'Asia/Kolkata',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: true,
      }) + ' IST'
    );
  } catch (e) {
    return String(dateStr);
  }
}
