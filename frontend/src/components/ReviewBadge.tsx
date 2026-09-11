export function ReviewBadge({ needsReview }: { needsReview: boolean }) {
  if (!needsReview) {
    return null;
  }
  return (
    <span className="review-badge" title="Low-confidence extraction — verify before trusting this record">
      Needs review
    </span>
  );
}
