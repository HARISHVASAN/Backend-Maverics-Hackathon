export default function DuplicateInfo({ complaint, onOpenComplaint }) {
  const status = complaint.duplicate_status || "NEW";

  if (status === "DUPLICATE") {
    return (
      <div className="dup-box dup-duplicate">
        <div className="dup-title">DUPLICATE</div>
        <div className="dup-line">
          Original:{" "}
          <button
            type="button"
            className="link-button"
            onClick={() => complaint.duplicate_of && onOpenComplaint(complaint.duplicate_of)}
          >
            {complaint.duplicate_of || "—"}
          </button>
        </div>
        {complaint.similarity_score != null && (
          <div className="dup-line">
            Similarity: {(complaint.similarity_score * 100).toFixed(0)}%
          </div>
        )}
      </div>
    );
  }

  if (status === "RELATED") {
    return (
      <div className="dup-box dup-related">
        <div className="dup-title">RELATED COMPLAINT</div>
        {complaint.duplicate_of && (
          <div className="dup-line">
            Related to:{" "}
            <button
              type="button"
              className="link-button"
              onClick={() => onOpenComplaint(complaint.duplicate_of)}
            >
              {complaint.duplicate_of}
            </button>
          </div>
        )}
        {complaint.similarity_score != null && (
          <div className="dup-line">
            Similarity: {(complaint.similarity_score * 100).toFixed(0)}%
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="dup-box dup-new">
      <div className="dup-title">NEW COMPLAINT</div>
    </div>
  );
}
