CREATE TABLE `authorization_queues` (
	`id` text PRIMARY KEY NOT NULL,
	`name` text NOT NULL,
	`description` text,
	`department` text DEFAULT 'General',
	`allowed_roles` text,
	`created_by` text,
	`created_at` text
);
--> statement-breakpoint
CREATE UNIQUE INDEX `authorization_queues_name_unique` ON `authorization_queues` (`name`);--> statement-breakpoint
CREATE TABLE `departments` (
	`id` text PRIMARY KEY NOT NULL,
	`name` text NOT NULL,
	`code` text NOT NULL,
	`type` text DEFAULT 'clinical' NOT NULL,
	`description` text,
	`enabled` integer DEFAULT true,
	`created_at` text,
	`last_modified_at` text,
	`last_modified_by` text
);
--> statement-breakpoint
CREATE UNIQUE INDEX `departments_code_unique` ON `departments` (`code`);