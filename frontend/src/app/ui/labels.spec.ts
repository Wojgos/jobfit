import { formatSalary } from './labels';

// toLocaleString uses a non-breaking space as the Polish thousands separator.
const normalize = (s: string) => s.replace(/\s/g, ' ');

describe('formatSalary', () => {
  it('formats a range with thousands separators', () => {
    expect(normalize(formatSalary(8000, 11000, 'PLN'))).toBe('8 000 – 11 000 PLN');
  });

  it('handles open ranges', () => {
    expect(normalize(formatSalary(null, 9000, 'EUR'))).toBe('up to 9 000 EUR');
    expect(normalize(formatSalary(6720, null, 'PLN'))).toBe('from 6 720 PLN');
    expect(formatSalary(null, null, 'PLN')).toBe('—');
  });
});
