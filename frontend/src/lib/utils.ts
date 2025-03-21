import {clsx, type ClassValue} from "clsx";
import {twMerge} from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const getTimeAgo = (dateString: string): string => {
  const date =
    dateString.charAt(dateString.length - 1) === "Z"
      ? new Date(dateString)
      : new Date(dateString + "Z");

  const now = new Date();

  const diffTime = Math.abs(now.getTime() - date.getTime());
  const diffSeconds = Math.floor(diffTime / 1000);

  // Less than a minute
  if (diffSeconds < 60) {
    return `${diffSeconds} ${diffSeconds === 1 ? "second" : "seconds"} ago`;
  }

  // Less than an hour
  const diffMinutes = Math.floor(diffSeconds / 60);
  if (diffMinutes < 60) {
    return `${diffMinutes} ${diffMinutes === 1 ? "minute" : "minutes"} ago`;
  }

  // Less than a day
  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 12) {
    return `${diffHours} ${diffHours === 1 ? "hour" : "hours"} ago`;
  }

  const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));

  if (diffDays === 0) {
    return "Today";
  } else if (diffDays === 1) {
    return "Yesterday";
  } else if (diffDays < 7) {
    return `${diffDays} days ago`;
  } else if (diffDays < 30) {
    const weeks = Math.floor(diffDays / 7);
    return `${weeks} ${weeks === 1 ? "week" : "weeks"} ago`;
  } else if (diffDays < 365) {
    const months = Math.floor(diffDays / 30);
    return `${months} ${months === 1 ? "month" : "months"} ago`;
  } else {
    const years = Math.floor(diffDays / 365);
    return `${years} ${years === 1 ? "year" : "years"} ago`;
  }
};

// Helper function to create a slug from website name
export const createKeyFromWebsite = (website: string) => {
  // Remove protocol and www if present
  let key = website.replace(/^(https?:\/\/)?(www\.)?/, "");
  // Remove domain extension
  key = key.replace(/\.[a-z]{2,}$/, "");
  // Convert to lowercase and replace non-alphanumeric with underscore
  key = key.toLowerCase().replace(/[^a-z0-9]/g, "_");
  // Add "_credentials" suffix
  return `${key}_credentials`;
};
