CREATE TABLE `audit_logs` (
	`id` text PRIMARY KEY NOT NULL,
	`entity_type` text NOT NULL,
	`entity_id` text NOT NULL,
	`action` text NOT NULL,
	`user_id` text NOT NULL,
	`timestamp` text NOT NULL,
	`details` text
);
--> statement-breakpoint
CREATE TABLE `orders` (
	`id` text PRIMARY KEY NOT NULL,
	`patient_id` text NOT NULL,
	`accession_number` text NOT NULL,
	`status` text NOT NULL,
	`order_by` text,
	`timestamp` text NOT NULL,
	`queue_id` text,
	`priority` text DEFAULT 'Routine',
	`completed_at` text,
	`test_ids` text,
	FOREIGN KEY (`patient_id`) REFERENCES `patients`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `orders_accession_number_unique` ON `orders` (`accession_number`);--> statement-breakpoint
CREATE TABLE `patients` (
	`id` text PRIMARY KEY NOT NULL,
	`first_name` text NOT NULL,
	`last_name` text NOT NULL,
	`dob` text NOT NULL,
	`gender` text NOT NULL,
	`mrn` text NOT NULL,
	`email` text,
	`phone` text,
	`address` text
);
--> statement-breakpoint
CREATE UNIQUE INDEX `patients_mrn_unique` ON `patients` (`mrn`);--> statement-breakpoint
CREATE TABLE `results` (
	`id` text PRIMARY KEY NOT NULL,
	`order_id` text NOT NULL,
	`test_id` text NOT NULL,
	`values` text,
	`result_flags` text,
	`status` text,
	`entered_by` text,
	`technical_validated_by` text,
	`clinical_verified_by` text,
	`timestamp` text NOT NULL,
	FOREIGN KEY (`order_id`) REFERENCES `orders`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE TABLE `specimens` (
	`id` text PRIMARY KEY NOT NULL,
	`order_id` text NOT NULL,
	`type` text NOT NULL,
	`container_id` text,
	`location` text,
	`collection_date` text,
	`status` text,
	FOREIGN KEY (`order_id`) REFERENCES `orders`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE TABLE `system_alerts` (
	`id` text PRIMARY KEY NOT NULL,
	`message` text NOT NULL,
	`type` text NOT NULL,
	`active` integer DEFAULT true,
	`created_at` text NOT NULL,
	`read_by` text,
	`timeout` integer
);
--> statement-breakpoint
CREATE TABLE `test_definitions` (
	`id` text PRIMARY KEY NOT NULL,
	`code` text NOT NULL,
	`name` text NOT NULL,
	`department` text NOT NULL,
	`units` text,
	`tat_hours` real,
	`active` integer DEFAULT true,
	`reference_range` text,
	`specimen_types` text,
	`methodology` text
);
--> statement-breakpoint
CREATE UNIQUE INDEX `test_definitions_code_unique` ON `test_definitions` (`code`);--> statement-breakpoint
CREATE TABLE `users` (
	`id` text PRIMARY KEY NOT NULL,
	`username` text NOT NULL,
	`password` text NOT NULL,
	`role` text NOT NULL,
	`name` text NOT NULL,
	`department` text,
	`email` text
);
--> statement-breakpoint
CREATE UNIQUE INDEX `users_username_unique` ON `users` (`username`);