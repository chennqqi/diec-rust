use std::mem;
use std::ptr;
use std::sync::Arc;
use std::sync::atomic::{AtomicUsize, Ordering};

use rquickjs::allocator::{Allocator, RustAllocator};

const ALLOC_ALIGNMENT: usize = mem::align_of::<u64>();
const ALLOC_HEADER_SIZE: usize = if mem::size_of::<usize>() > ALLOC_ALIGNMENT {
    mem::size_of::<usize>()
} else {
    ALLOC_ALIGNMENT
};

#[derive(Default)]
pub(crate) struct TrackingAllocatorStats {
    live_bytes: AtomicUsize,
    high_water_bytes: AtomicUsize,
    denied_allocation_count: AtomicUsize,
}

impl TrackingAllocatorStats {
    pub(crate) fn live_bytes(&self) -> usize {
        self.live_bytes.load(Ordering::Relaxed)
    }

    pub(crate) fn high_water_bytes(&self) -> usize {
        self.high_water_bytes.load(Ordering::Relaxed)
    }

    pub(crate) fn denied_allocation_count(&self) -> usize {
        self.denied_allocation_count.load(Ordering::Relaxed)
    }

    fn deny(&self) {
        self.denied_allocation_count.fetch_add(1, Ordering::Relaxed);
    }

    fn replace_live(&self, previous_size: usize, new_size: usize) {
        let live = self.live_bytes.load(Ordering::Relaxed);
        let next = live - previous_size + new_size;
        self.live_bytes.store(next, Ordering::Relaxed);
        self.high_water_bytes.fetch_max(next, Ordering::Relaxed);
    }
}

pub(crate) struct TrackingLimitAllocator {
    maximum_live_bytes: usize,
    stats: Arc<TrackingAllocatorStats>,
}

impl TrackingLimitAllocator {
    pub(crate) fn new(maximum_live_bytes: usize) -> (Self, Arc<TrackingAllocatorStats>) {
        let stats = Arc::new(TrackingAllocatorStats::default());
        (
            Self {
                maximum_live_bytes,
                stats: Arc::clone(&stats),
            },
            stats,
        )
    }

    fn accounted_size_for_request(size: usize) -> Option<usize> {
        let rounded_payload = size
            .checked_add(ALLOC_ALIGNMENT - 1)
            .map(|value| value / ALLOC_ALIGNMENT * ALLOC_ALIGNMENT)?;
        rounded_payload.checked_add(ALLOC_HEADER_SIZE)
    }

    fn accounted_size_for_allocation(allocation: *mut u8) -> usize {
        // SAFETY: callers invoke this helper only for a live pointer returned by
        // the delegated `RustAllocator`. Its successful `Layout` construction
        // already proved that usable payload plus this exact header fits `usize`.
        let usable = unsafe { RustAllocator::usable_size(allocation) };
        usable + ALLOC_HEADER_SIZE
    }

    fn projected_live(&self, previous_size: usize, new_size: usize) -> Option<usize> {
        self.stats
            .live_bytes()
            .checked_sub(previous_size)?
            .checked_add(new_size)
            .filter(|projected| *projected <= self.maximum_live_bytes)
    }

    fn allocate(
        &mut self,
        requested_size: usize,
        allocate: impl FnOnce(&mut RustAllocator) -> *mut u8,
    ) -> *mut u8 {
        let Some(expected_size) = Self::accounted_size_for_request(requested_size) else {
            self.stats.deny();
            return ptr::null_mut();
        };
        if self.projected_live(0, expected_size).is_none() {
            self.stats.deny();
            return ptr::null_mut();
        }
        let mut allocator = RustAllocator;
        let allocation = allocate(&mut allocator);
        if allocation.is_null() {
            return allocation;
        }
        // SAFETY: `allocation` was returned by this `RustAllocator` call and has not
        // been freed or reallocated.
        let actual_size = Self::accounted_size_for_allocation(allocation);
        if self.projected_live(0, actual_size).is_none() {
            // SAFETY: the pointer was returned by `RustAllocator` immediately above
            // and ownership has not escaped this function.
            unsafe { RustAllocator.dealloc(allocation) };
            self.stats.deny();
            return ptr::null_mut();
        }
        self.stats.replace_live(0, actual_size);
        allocation
    }
}

// SAFETY: every allocation operation delegates pointer creation, layout metadata,
// reallocation, and destruction to the pinned `RustAllocator`. This wrapper never
// changes returned pointers or their alignment. It only reads `usable_size` while
// the allocation is live and updates counters. A denied realloc returns null before
// delegating, preserving ownership of the original allocation.
unsafe impl Allocator for TrackingLimitAllocator {
    fn alloc(&mut self, size: usize) -> *mut u8 {
        self.allocate(size, |allocator| allocator.alloc(size))
    }

    fn calloc(&mut self, count: usize, size: usize) -> *mut u8 {
        if count == 0 || size == 0 {
            return ptr::null_mut();
        }
        let Some(total_size) = count.checked_mul(size) else {
            self.stats.deny();
            return ptr::null_mut();
        };
        self.allocate(total_size, |allocator| allocator.calloc(count, size))
    }

    unsafe fn dealloc(&mut self, allocation: *mut u8) {
        // SAFETY: the trait caller guarantees that `allocation` is live and was
        // created by this allocator; this wrapper delegates to the same pinned
        // `RustAllocator` instance semantics used for creation.
        let size = Self::accounted_size_for_allocation(allocation);
        self.stats.replace_live(size, 0);
        unsafe { RustAllocator.dealloc(allocation) };
    }

    unsafe fn realloc(&mut self, allocation: *mut u8, new_size: usize) -> *mut u8 {
        if allocation.is_null() {
            return self.alloc(new_size);
        }
        // SAFETY: the trait caller guarantees that `allocation` is live and was
        // created by this allocator.
        let previous_size = Self::accounted_size_for_allocation(allocation);
        let Some(expected_size) = Self::accounted_size_for_request(new_size) else {
            self.stats.deny();
            return ptr::null_mut();
        };
        if self.projected_live(previous_size, expected_size).is_none() {
            self.stats.deny();
            return ptr::null_mut();
        }
        // SAFETY: the pointer and requested size satisfy the delegated allocator's
        // contract. On failure `RustAllocator` leaves the original allocation live.
        let resized = unsafe { RustAllocator.realloc(allocation, new_size) };
        if resized.is_null() {
            return resized;
        }
        // SAFETY: `resized` is the live pointer returned by the successful realloc.
        let actual_size = Self::accounted_size_for_allocation(resized);
        self.stats.replace_live(previous_size, actual_size);
        resized
    }

    unsafe fn usable_size(allocation: *mut u8) -> usize
    where
        Self: Sized,
    {
        // SAFETY: the trait caller guarantees that `allocation` is live and belongs
        // to this allocator, which delegates its layout to `RustAllocator`.
        unsafe { RustAllocator::usable_size(allocation) }
    }
}

#[cfg(test)]
mod tests {
    use rquickjs::allocator::Allocator;

    use super::{ALLOC_ALIGNMENT, ALLOC_HEADER_SIZE, TrackingLimitAllocator};

    #[test]
    fn accounted_size_rejects_request_that_would_overflow_allocator_header() {
        assert_eq!(
            TrackingLimitAllocator::accounted_size_for_request(usize::MAX),
            None
        );
    }

    #[test]
    fn allocator_limit_boundary_counts_alignment_and_header() {
        let exact_limit = ALLOC_HEADER_SIZE + ALLOC_ALIGNMENT;
        let (mut exact, exact_stats) = TrackingLimitAllocator::new(exact_limit);
        let exact_allocation = exact.alloc(ALLOC_ALIGNMENT);
        assert!(!exact_allocation.is_null());
        assert_eq!(exact_stats.live_bytes(), exact_limit);
        assert_eq!(exact_stats.high_water_bytes(), exact_limit);
        assert_eq!(exact_stats.denied_allocation_count(), 0);
        // SAFETY: the pointer is live and belongs to `exact`.
        unsafe { exact.dealloc(exact_allocation) };
        assert_eq!(exact_stats.live_bytes(), 0);

        let (mut limit_minus_one, below_stats) = TrackingLimitAllocator::new(exact_limit - 1);
        assert!(limit_minus_one.alloc(ALLOC_ALIGNMENT).is_null());
        assert_eq!(below_stats.live_bytes(), 0);
        assert_eq!(below_stats.denied_allocation_count(), 1);

        let (mut payload_plus_one, above_stats) = TrackingLimitAllocator::new(exact_limit);
        assert!(payload_plus_one.alloc(ALLOC_ALIGNMENT + 1).is_null());
        assert_eq!(above_stats.live_bytes(), 0);
        assert_eq!(above_stats.denied_allocation_count(), 1);
    }

    #[test]
    fn denied_realloc_preserves_original_allocation_and_accounting() {
        let exact_limit = ALLOC_HEADER_SIZE + ALLOC_ALIGNMENT;
        let (mut allocator, stats) = TrackingLimitAllocator::new(exact_limit);
        let allocation = allocator.alloc(ALLOC_ALIGNMENT);
        assert!(!allocation.is_null());

        // SAFETY: `allocation` is live and belongs to `allocator`. A null return
        // preserves the original allocation according to the allocator contract.
        let resized = unsafe { allocator.realloc(allocation, ALLOC_ALIGNMENT + 1) };
        assert!(resized.is_null());
        assert_eq!(stats.live_bytes(), exact_limit);
        assert_eq!(stats.high_water_bytes(), exact_limit);
        assert_eq!(stats.denied_allocation_count(), 1);

        // SAFETY: the failed realloc left the original pointer live.
        unsafe { allocator.dealloc(allocation) };
        assert_eq!(stats.live_bytes(), 0);
    }
}
