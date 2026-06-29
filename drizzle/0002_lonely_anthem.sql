CREATE TABLE `billing_items` (
	`id` text PRIMARY KEY NOT NULL,
	`code` text NOT NULL,
	`name` text NOT NULL,
	`price` real NOT NULL,
	`active` integer DEFAULT true
);
--> statement-breakpoint
CREATE UNIQUE INDEX `billing_items_code_unique` ON `billing_items` (`code`);--> statement-breakpoint
CREATE TABLE `inventory_items` (
	`id` text PRIMARY KEY NOT NULL,
	`name` text NOT NULL,
	`lot_number` text,
	`expiration_date` text,
	`quantity` integer DEFAULT 0 NOT NULL,
	`unit` text NOT NULL,
	`min_threshold` integer DEFAULT 10,
	`location` text
);
--> statement-breakpoint
CREATE TABLE `inventory_transactions` (
	`id` text PRIMARY KEY NOT NULL,
	`item_id` text NOT NULL,
	`change` integer NOT NULL,
	`reason` text NOT NULL,
	`user_id` text NOT NULL,
	`timestamp` text NOT NULL,
	FOREIGN KEY (`item_id`) REFERENCES `inventory_items`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE TABLE `invoices` (
	`id` text PRIMARY KEY NOT NULL,
	`order_id` text NOT NULL,
	`total_amount` real NOT NULL,
	`status` text NOT NULL,
	`created_at` text NOT NULL,
	`items` text,
	FOREIGN KEY (`order_id`) REFERENCES `orders`(`id`) ON UPDATE no action ON DELETE no action
);
